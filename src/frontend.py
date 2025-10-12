import streamlit as st
from utils.process_files import process_uploaded_pdfs
from utils.index_files import create_qdrant_vector_store
from utils.final_block_rag import create_langgraph_app, run_rag_with_langgraph
from utils.retriever import create_retriever

import os
import io
from helper import project_root
from config import LOCAL_FOLDER, COLLECTION_NAME
import json

# do streamlit front end for simplicity, that passes on uploaded documents to backend for vector store.
# also passes on user query to rag handler and gets back response, and provides saving options.


def display_chat(history):
    """
    Displays the chat history in the Streamlit app, handling structured assistant output.
    """
    for entry in history:
        if entry["role"] == "user":
            with st.chat_message("user"):
                st.write(entry["content"])

        elif entry["role"] == "assistant":
            with st.chat_message("assistant"):
                # Display the main answer
                st.write(entry["content"]["answer"])

                # Get confidence score, defaulting to None if not present
                confidence_score = (
                    entry["content"].get("confidence", {}).get("confidence_score")
                )

                # Check if confidence score exists and display it
                if confidence_score is not None:
                    if confidence_score < 0:
                        confidence_score = 0
                    # Use markdown with HTML to float the text to the right and make it smaller
                    st.markdown(
                        f"""
                        <div style="text-align: right; font-size: 0.8em; color: gray;">
                            Confidence: {confidence_score}%
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                # Consolidate and display the citations
                if entry["content"].get("citations", None):
                    # Use a dictionary to group citations by document name only
                    consolidated_citations = {}

                    # Store a mapping of doc_name to a sample doc_num for display
                    doc_num_map = {}

                    for citation in entry["content"]["citations"]:
                        doc_name = citation["document_name"]
                        doc_num = citation["document_number"]

                        if doc_name not in consolidated_citations:
                            consolidated_citations[doc_name] = []
                            doc_num_map[doc_name] = (
                                doc_num  # Store the number for later display
                            )

                        consolidated_citations[doc_name].extend(
                            citation["page_numbers"]
                        )

                    with st.expander("References"):
                        # Iterate through the consolidated dictionary
                        for doc_name, page_numbers in consolidated_citations.items():
                            # Remove duplicates and sort the page numbers
                            unique_pages = sorted(set(page_numbers))
                            page_str = ", ".join(map(str, unique_pages))

                            # Get the document number from our map
                            doc_num = doc_num_map.get(doc_name, "N/A")

                            st.markdown(f"[{doc_num}] {doc_name}, Pages: {page_str}\n")


def convert_to_markdown(history):
    markdown_text = ""
    for entry in history:
        if entry["role"] == "user":
            markdown_text += f"**User:** {entry['content']}\n"

        elif entry["role"] == "assistant":
            markdown_text += (
                f"**Assistant:**\n  **Response :** {entry['content']['answer']}"
            )

            # Consolidate citations
            if entry["content"].get("citations", None):
                # Use a dictionary to group citations by document name only
                consolidated_citations = {}

                # Store a mapping of doc_name to a sample doc_num for display
                doc_num_map = {}

                for citation in entry["content"]["citations"]:
                    doc_name = citation["document_name"]
                    doc_num = citation["document_number"]

                    if doc_name not in consolidated_citations:
                        consolidated_citations[doc_name] = []
                        doc_num_map[doc_name] = (
                            doc_num  # Store the number for later display
                        )

                    consolidated_citations[doc_name].extend(citation["page_numbers"])

                markdown_text += "\n  **Ref:**"
                for doc_name, page_numbers in consolidated_citations.items():
                    # Remove duplicates and sort the page numbers
                    unique_pages = sorted(set(page_numbers))
                    page_str = ", ".join(map(str, unique_pages))

                    # Get the document number from our map
                    doc_num = doc_num_map.get(doc_name, "N/A")
                    markdown_text += f"[{doc_num}] {doc_name}, Pages: {page_str}\n"

        markdown_text += "\n"

    return markdown_text


def get_user_input():
    """Gets user input from the Streamlit input box."""
    return st.chat_input("Enter your message here...")


def initialize():
    if "start_flag" not in st.session_state:
        st.session_state.start_flag = False
    # Initialize chat history in session state
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = [
            {"role": "system", "content": "Please answer any question respectfully"}
        ]
    if "vector_store" not in st.session_state:
        st.session_state.vector_store = None
        st.session_state.document_chunks = None

    st.session_state.is_follow_up = False
    st.session_state.reset_history = False
    st.session_state.markdown_file = ""

    if "rag_app" not in st.session_state:
        st.session_state["rag_app"] = None

    if "retriever" not in st.session_state:
        st.session_state["retriever"] = None


# A function to handle the user's query
def handle_query_and_run_rag(query):
    # Check if the vector store and chunks are in session state

    if "rag_app" in st.session_state and query is not None:
        app = st.session_state.rag_app
        graph_state = {
            "question": query,
            "chat_history": st.session_state["chat_history"],
            "documents": st.session_state["document_chunks"],
            "answer": "",
            "enhanced_question": "",
            "is_follow_up": st.session_state["is_follow_up"],
            "reset_history": st.session_state["reset_history"],
        }
        # Pass the components to the RAG function
        result = run_rag_with_langgraph(graph_state, app)
        if type(result) is not dict:
            result = json.loads(result)
        return result["answer"]
    else:
        st.warning("Please create the vector store first by clicking the button.")


@st.cache_data
def cached_process_files(uploaded_files):
    """
    A wrapper function that calls the backend function and is
    decorated with st.cache_data.
    """
    # Extract the file content (bytes) from the UploadedFile objects

    file_path = os.path.join(project_root, LOCAL_FOLDER, COLLECTION_NAME)
    os.makedirs(file_path, exist_ok=True)
    file_paths = [None] * len(uploaded_files)
    for i, file in enumerate(uploaded_files):
        file_bytes = file.getvalue()
        file_paths[i] = file_path + os.sep + file.name
        with open(file_paths[i], "wb") as f:
            f.write(file_bytes)

    # Pass the content to the backend function
    return process_uploaded_pdfs(file_paths, extract_metadata=True)


def main():
    with st.sidebar:
        st.header("Upload PDFs")
        uploaded_files = st.file_uploader(
            "Choose PDF files to upload", type="pdf", accept_multiple_files=True
        )

        if uploaded_files:
            st.success(f"Successfully uploaded {len(uploaded_files)} file(s).")

            with st.spinner("Processing PDFs..."):
                documents = cached_process_files(uploaded_files)

            st.write("---")
            st.subheader("📚 Index Documents")

            if documents:
                st.write(f"Ingested {len(documents)} document(s) from the PDFs.")
                st.info("The documents are now ready to index.")
            else:
                st.warning("No documents were extracted from the uploaded files.")

    st.title("RAG Chatbot")

    if st.button("Create Index"):
        # Call the backend function when the button is pressed
        vec_db, docs = create_qdrant_vector_store(True)
        st.session_state["vector_store"] = vec_db
        st.session_state["document_chunks"] = docs
        st.info("Index generation successfull.....")
        st.session_state.retriever = create_retriever(vec_db, docs)
        st.info("retriever created....")
        st.session_state.rag_app = create_langgraph_app(st.session_state.retriever)
        st.info("RAG setup complete.")

    # Get user input
    user_input = get_user_input()

    if "chat_history" not in st.session_state:
        initialize()

    if user_input and user_input.lower() not in {"exit", "quit"}:
        st.session_state.start_flag = True
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        response = handle_query_and_run_rag(user_input)

        # Update session state with the new full conversation
        st.session_state.chat_history.append({"role": "assistant", "content": response})
    elif (
        st.session_state.start_flag
        and user_input
        and user_input.lower() in {"exit", "quit"}
    ):
        print(
            f"Inside the else block: Flag: {st.session_state.start_flag}, user question: {user_input}"
        )
        if user_input is not None:
            st.session_state.chat_history.append(
                {"role": "user", "content": user_input}
            )
            st.session_state.chat_history.append(
                {
                    "role": "assistant",
                    "content": {"answer": "Thanks for chatting, Have a great day."},
                }
            )

        markdown_text = convert_to_markdown(st.session_state.chat_history)

        # Convert to bytes
        markdown_bytes = markdown_text.strip().encode()

        # Create a BytesIO object
        markdown_file = io.BytesIO(markdown_bytes)

        st.session_state.markdown_file = markdown_file  # store to use later

        st.session_state.start_flag = False

    display_chat(st.session_state.chat_history)
    if st.session_state.markdown_file != "":
        st.download_button(
            label="Download Chat History",
            data=st.session_state.markdown_file,
            file_name="chat_history.md",
            mime="text/markdown",
            key="download_button",
            on_click=initialize(),
        )


if __name__ == "__main__":
    main()
