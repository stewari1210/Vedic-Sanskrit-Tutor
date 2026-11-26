# Gazetteer Disambiguation Audit (`vaśa`, `āyu`, `parśu`, `kāśi`, `pūru`)

Scanned **53,263** indexed + dry-run lines across `local_store/`.
Raw bare-stem substring matching mixed proper names with common nouns (*vaśa/vaśā*, *āyus*, *parśu/pārśva*, *kāś-/Kāśyapa*, *pūruṣa*).

## Summary Counts: Raw Substring vs. Disambiguated Proper-Name Rules

| Entry | Raw Substring Hits | Disambiguated Name Hits | Strategy |
|---|---:|---:|---|
| vaśa (`vasa`) | 1,267 | 3 | Curated exact / context-gated (`वशमश्व्य`, `वशो अश्व्य`, `वशोशीनर`, `सवशोशीनर` — removes bare `वश`) |
| āyu (`ayu`) | 1,034 | 9 | Context-gated ONLY (`आयुं/आयुर्/आयुः/आयोः/आयव` + co-occurrence of `पुरूरव`/`उर्वश`/`अमावसु`/`कुत्स`/`अतिथिग्व`) |
| parśu (`parsu`) | 88 | 3 | Context-gated ONLY (`पर्शव`/`पर्शो`/`स्पर्शव`/`पर्शुर्ह नाम` + co-occurrence of `मानवी`/`गन्धार`/`अरट्ट`/`पृथु`/`तिरश्चि`; removes bare `पर्शु` 'sickle' and `पार्श्व` 'side/flank') |
| kāśi (`kasi`) | 39 | 8 | Curated exact (`काशिभ्य`, `काशिकौशल`, `काशिविदेह`, `काशीना`, `काशयो`, `काश्यस्य`, `काश्यं`, `काश्यः`, `काश्यो`) — excludes `काश्यप`, `आकाश्य`, `अवकाश्य`, `काशिनी` |
| pūru (`puru`) | 139 | 19 | Curated exact (`पूरुं`, `पूरुम्`, `पूरुभ्य`, `पूरुर्`, `पूरुः`, `पूरवे`, `पूरवो`, `पौरव`) — excludes `पूरुष` (*pūruṣa* 'man/person') and `पूरुहूत` ('much-invoked') |

---

## Labelled Sample Hits (`name` vs. `common noun`)

### vaśa (`vasa`)
- **Strategy:** Curated exact / context-gated (`वशमश्व्य`, `वशो अश्व्य`, `वशोशीनर`, `सवशोशीनर` — removes bare `वश`)

| Citation | Label | Excerpt | Notes |
|---|---|---|---|
| `RV 8.046.21` | **name** | ेवः पूर्तमाददे । यथा चिद्वशो अश्व्यः पृथुश्रवसि कानीते३ऽस्या व्युष् | Vaśa Aśvya (personal donor-patron name: `वशो अश्व्यः`) |
| `RV 1.112.10` | **name** | ळ्ह आजावजिन्वतम् । याभिर्वशमश्व्यं प्रेणिमावतं ताभिरू षु ऊतिभिरश्वि | Vaśa Aśvya (`वशमश्व्यम्`) |
| `AB 8.14.3` | **name** | च कुरुपञ्चालानां राजानः सवशोशीनराणां राज्यायैव ते भिषिच्यन्ते , राज | Vaśa ethnonym paired with Uśīnaras (`सवशोशीनराणां`) |
| `GB 1.2.10` | **name** | िकौशलेषु शाल्वमत्स्येषु सवशोशीनरेषूदीच्येष्व् अन्नम् अदन्तीति अथ वय | Vaśa-Uśīnaras in list of peoples (`सवशोशीनरेषूदीच्येष्व्`) |
| `AVP 1.40.1` | **common noun** | ष्टा च पूषा च ममैव सविता वशे | `वशे मम` = 'under my control / will' (*vaśe*) |
| `AVP 5.5.1` | **common noun** | पृथिवी वशा साग्निं गर्भं दधे सेमं पाहि तस्यै ते व | `पृथिवी वशा` = 'the Earth is a barren/mystic cow' (*vaśā*) |
| `TB 1.2.5.41` | **common noun** | वरुन्धे । आदित्याम् अविं वशाम् आलभन्ते । इयं वा अदितिः । अस्याम् एव | `वशं गच्छति` / ritual control (*vaśam*), not person/tribe |

### āyu (`ayu`)
- **Strategy:** Context-gated ONLY (`आयुं/आयुर्/आयुः/आयोः/आयव` + co-occurrence of `पुरूरव`/`उर्वश`/`अमावसु`/`कुत्स`/`अतिथिग्व`)

| Citation | Label | Excerpt | Notes |
|---|---|---|---|
| `MS 1.6.12` | **name** | शीम् अविन्दत देवीं तस्या आयुर् अजायत स देवान्त् स्वर्गं लोकं यत्तो न | Āyu, son of Purūravas & Urvaśī (`उर्वशीम् … तस्या आयुर् अजायत`) |
| `MS 1.2.7` | **name** | वृषणौ स्थ उर्वश्य् अस्य् आयुर् असि पुरूरवा असि गायत्रम् असि त्रिष्टु | Ritual formula identifying churning stick with Āyu alongside Purūravas & Urvaśī |
| `AVP 5.27.2` | **name** | वददहिम् अहिराजन्तम् ओजसा आयुं चित् कुत्सम् अतिथिग्वम् अर्दय वि निकिल | King/hero Āyu alongside Kutsa & Atithigva (`आयुं चित् कुत्सम् अतिथिग्वम्`) |
| `AVŚ 20.21.10` | **name** | अस्मै कुत्सम् अतिथिग्वम् आयुं महे राज्ञे यूने अरन्धनायः | Āyu alongside Kutsa & Atithigva (`कुत्सम् अतिथिग्वम् आयुं`) |
| `AB 1.5.6` | **common noun** | सर्वम् आयुर् एति य एवं विद्वान् उष्णिहौ कुरुते | `सर्वम् आयुर् एति` = 'attains a full lifespan (*āyuḥ*)' |
| `TB 1.1.1.3` | **common noun** | ंधत्तं तां मे जिन्वतम् । आयुः स्थ आयुर् मे धत्तम् । आयुर् यज्ञाय धत् | `आयुर् यज्ञपतये` = 'lifespan (*āyuḥ*)' |
| `AVP 1.56.2` | **common noun** | उद् धर्षन्तां मघवन्न् आयुधान्य् उत् सत्वनां मामकानां मनांसि उद् ध | `आयुधान्य्` = 'weapons (*āyudhāni*)' (substring match!) |

### parśu (`parsu`)
- **Strategy:** Context-gated ONLY (`पर्शव`/`पर्शो`/`स्पर्शव`/`पर्शुर्ह नाम` + co-occurrence of `मानवी`/`गन्धार`/`अरट्ट`/`पृथु`/`तिरश्चि`; removes bare `पर्शु` 'sickle' and `पार्श्व` 'side/flank')

| Citation | Label | Excerpt | Notes |
|---|---|---|---|
| `RV 10.086.23` | **name** | पर्शुर्ह नाम मानवी साकं ससूव विंशतिम् । भद्रं | Parśu Mānavī (`पर्शुर्ह नाम मानवी`) |
| `AVŚ 20.126.23` | **name** | पर्शुर् ह नाम मानवी साकं ससूव विंशतिम् भद्रं  | Parśu Mānavī (`पर्शुर् ह नाम मानवी`) |
| `BĀU 1.1.1` | **common noun** | उदरं पृथिवी पाजस्यं दिशः पार्श्वे अवान्तरदिशः पर्शव ऋतवो ङ्गानि मासाश् च | `दिशः पार्श्वे अवान्तरदिशः पर्शव` = 'ribs (*parśavaḥ*) & sides (*pārśve*)' |
| `GB 1.5.3` | **common noun** | म् तस्माद् उदरम् एकविंशः पार्श्वे त्रिणवस् त्रयोदशान्याः पर्शवस् त्रयोदश | `पार्श्वे … पर्शवस्` = anatomical 'sides / ribs' |
| `AVŚ 12.3.31` | **common noun** | प्र यछ पर्शुं त्वरया हरौसम् अहिंसन्त ओषधीर् दान्तु प | `प्र यछ पर्शुं` = 'sickle / reaping-knife (*parśu*)' |
| `TB 3.2.2.7` | **common noun** | ा सवितुः प्रसव इत्य् अश्वपर्शुम् आदत्ते प्रसूत्यै । अश्विनोर् बाहुभ्या | `अश्वपर्शुम् आदत्ते` = 'horse-rib (*aśva-parśu*)' |

### kāśi (`kasi`)
- **Strategy:** Curated exact (`काशिभ्य`, `काशिकौशल`, `काशिविदेह`, `काशीना`, `काशयो`, `काश्यस्य`, `काश्यं`, `काश्यः`, `काश्यो`) — excludes `काश्यप`, `आकाश्य`, `अवकाश्य`, `काशिनी`

| Citation | Label | Excerpt | Notes |
|---|---|---|---|
| `BĀU 2.1.1` | **name** | ग्य आस स होवाचाजातशत्रुं काश्यं -- ब्रह्म ते ब्रवाणीति स होवाचाजातशत्र | King Ajātaśatru of Kāśi (`अजातशत्रुं काश्यं`) |
| `BĀU 3.8.2` | **name** |  वै त्वा याज्ञवल्क्य यथा काश्यो वा वैदेहो वोग्रपुत्र उज्ज्यं धनुर् अधि | `काश्यो वा वैदेहो` = 'Kāśi or Videha champion' |
| `GB 1.2.10` | **name** | रुपञ्चालेष्व् अङ्गमगधेषु काशिकौशलेषु शाल्वमत्स्येषु सवशोशीनरेषूदीच्ये | `काशिकौशलेषु` = peoples list (Kāśis and Kosalas) |
| `AVP 12.2.2` | **name** | गन्धारिभ्यो मूजवद्भ्यः काशिभ्यो मगधेभ्यः जने प्रियम् इव शेवधिं तक्म | `काशिभ्यो मगधेभ्यः` = eastern peoples (Kāśis, Magadhas) |
| `SB 13.5.4.19` | **name** | ेन शतानीकः सात्राजित ईजे काश्यस्याश्वमादाय ततो हैतर्दवाक्काशयोऽग्नीन्न | `काश्यस्याश्वमादाय` = Kāśi king's sacrificial horse |
| `JUB 3.7.3` | **common noun** |  ऽग्निर् इन्द्रायेन्द्रः काश्यपाय काश्यप ऋश्यशृङ्गाय काश्यपाय र्श्यशृङ | `काश्यप` = Kāśyapa gotra/patron (substring collision on `काश्य`) |
| `AVP 3.28.5` | **common noun** | ्छिन्नेव शंगुणी चक्षुर् आकाश्यं भीमं मांपश्यम् अभिरोरुदम् | `आकाश्यं` = verb/adj. from *kāś* 'to look/appear' |
| `SB 1.3.1.20` | **common noun** | ेव विलाप्य प्रागुदाहरत्यवकाश्य पत्नीं यस्यो पत्नी न भवत्यग्र एव तस्याह | `अवकाश्य पत्नीं` = causative gerund from *ava-kāś* 'make look' |
| `AVP 14.3.8` | **common noun** | रुद्र शिवा तनूर् अघोरापापकाशिनी तया नस् तन्वा शन्तमया गिरिशन्ताभि चाक | `अपापकाशिनी` = 'appearing free from evil' |

### pūru (`puru`)
- **Strategy:** Curated exact (`पूरुं`, `पूरुम्`, `पूरुभ्य`, `पूरुर्`, `पूरुः`, `पूरवे`, `पूरवो`, `पौरव`) — excludes `पूरुष` (*pūruṣa* 'man/person') and `पूरुहूत` ('much-invoked')

| Citation | Label | Excerpt | Notes |
|---|---|---|---|
| `RV 7.018.13` | **name** | ्य तृत्सवे गयं भाग्जेष्म पूरुं विदथे मृध्रवाचम् | `पूरुं विदथे मृध्रवाचम्` = Pūru tribe defeated at Paruṣṇī |
| `RV 7.008.04` | **name** |  रोचते बृहद्भाः । अभि यः पूरुं पृतनासु तस्थौ द्युतानो दैव्यो अतिथिः श | `अभि यः पूरुं पृतनासु तस्थौ` = Pūru in battles |
| `MS 2.7.10` | **name** | न रोचते बृहद् भाः अभि यः पूरुं पृतनासु तस्थौ दीदाय दैव्यो अतिथिः शिवो | Mantras quoting `अभि यः पूरुं पृतनासु तस्थौ` |
| `AVŚ 20.37.3` | **name** | क्षेत्रसाता वृत्रहत्येषु पूरुम् | `वृत्रहत्येषु पूरुम्` = Pūru tribe |
| `AVP 1.10.4` | **common noun** | हंस्य् अश्वं यदि गां यदि पूरुषम् सीसेन विध्यामस् त्वा यथा नो सो अवीरह | `पूरुषम्` = 'person/man (*pūruṣa*)' (substring collision!) |
| `AVP 18.55.6` | **common noun** | ्रासि विश्ववित् सर्ववित् पूरुहूतस् त्वम् इन्द्रेमं सुहव स्तोमम् एरयस् | `पूरुहूतस्` = 'much-invoked (*pūruhūta*)' epithet of Indra |
| `TB 1.5.10.47` | **common noun** | ः । तद् एतत् त्रिशलं त्रिपूरुषम् । तस्मात् तं त्रिवितस्तं खनन्ति । स  | `त्रिपूरुषम्` = 'three man-lengths (*puruṣa*)' |
| `Nir 7.23` | **common noun** | ृसभस्य वर्षितृ अपाम् यम् पूरु प् पूरयितव्या मनुष्या वृत्रहनम् मेघहनम् | Etymological gloss `पूरयितव्या मनुष्याः` on `पूरु` |

