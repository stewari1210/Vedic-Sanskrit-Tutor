# Taittirīya Āraṇyaka Overlap Comparison — Sanskrit Library vs. Manual `sanskritdocuments.org` ITX

Compares accent-stripped Devanāgarī words & section numbering across all overlapping regions:
- `TA 1.1–6` (`titus/vedic/ta1`, accented vs ITX accented)
- `TA 4` (`titus/vedic/ta4`, accented vs ITX accented)
- `TA 5` (`titus/vedic/ta5`, accented vs ITX accented)
- `TA 7–9` (`titus/vedic/taittup`, unaccented vs ITX accented)

| Region | SL Anuvākas | ITX Anuvākas | SL Units | ITX Units | Word Jaccard | Shared / Union Words | Key Observed Differences |
|---|---:|---:|---:|---:|---:|---:|---|
| `TA 1.1–6` | 6 | 6 | 23 | 19 | 0.420 | 288/685 | Both cover Anuvākas 1–6; SL includes final pratīka words in unit 4 of anuvāka (`सुतौषधयो द्वे च`), ITX separates after `|| 0| 1| a| v||`; ITX joins internal sandhi without spaces. |
| `TA 4` | 42 | 42 | 42 | 93 | 0.450 | 1019/2262 | Exact 42=42 anuvāka alignment; ITX splits into 93 pañcāśat/kaṇḍikā markers (`v`), SL groups by anuvāka (`TA 4.A`); SL marks word boundaries whereas ITX preserves continuous Taittirīya sandhi (`संवथ्सर` vs `संवत्सर`). |
| `TA 5` | 12 | 12 | 12 | 108 | 0.348 | 989/2841 | Exact 12=12 anuvāka alignment; ITX splits into 108 pañcāśat/kaṇḍikā markers (`v`), SL groups by anuvāka (`TA 5.A`); SL marks word boundaries whereas ITX preserves continuous Taittirīya sandhi (`संवथ्सर` vs `संवत्सर`). |
| `TA 7` | 12 | 12 | 23 | 23 | 0.777 | 380/489 | Exact anuvāka alignment; SL `taittup` is unaccented while ITX has full Vedic svara marks (`॑ ॒ ᳚`) + Taittirīya anusvāra-sandhi. |
| `TA 8` | 9 | 9 | 13 | 9 | 0.772 | 291/377 | Exact anuvāka alignment; SL `taittup` is unaccented while ITX has full Vedic svara marks (`॑ ॒ ᳚`) + Taittirīya anusvāra-sandhi. |
| `TA 9` | 10 | 10 | 15 | 10 | 0.679 | 180/265 | Exact anuvāka alignment; SL `taittup` is unaccented while ITX has full Vedic svara marks (`॑ ॒ ᳚`) + Taittirīya anusvāra-sandhi. |

## Observed Anuvāka-Level Differences & Text Samples

### TA 1.1–6 — Anuvāka 1 (SL `4` unit(s) vs ITX `3` unit(s))
- **SL (unaccented view):** भद्रं कर्णेभिः शृणुयाम देवाः । भद्रं पश्येमाक्षभिर् यजत्राः । स्थिरैर् अङ्गैस् तुष्टुवांसस् तनूभिः । व्यशेम देवहितं यद् आयुः । स्वस्ति न इन्द्रो वृद्धश्रवाः । स्वस्ति नः पूषा विश्व
- **ITX (unaccented view):** ओं भद्रं कर्णेभिः शृणुयाम देवाः । भद्रं पश्येमाक्षभिर्यजत्राः । स्थिरैरङ्गैस्तुष्टुवांसस्तनूभिः । व्यशेम देवहितं यदायुः । स्वस्ति न इन्द्रो वृद्धश्रवाः । स्वस्ति नः पूषा विश्ववेदाः

### TA 4 — Anuvāka 1 (SL `1` unit(s) vs ITX `1` unit(s))
- **SL (unaccented view):** नमो वाचे या चोदिता या चानुदिता तस्यै वाचे नमो नमो वाचे नमो वाचस्पतये नम ऋषिभ्यो मन्त्रकृद्भ्यो मन्त्रपतिभ्यो मा माम् ऋषयो मन्त्रकृतो मन्त्रपतयः परा दुर् मा ऽहम् ऋषीन् मन्त्रकृतो मन
- **ITX (unaccented view):** नमो वाचे या चोदिता या चानुदिता तस्यै वाचे नमो नमो वाचे नमो वाचस्पतये नम ऋषिभ्यो मन्त्रकृद्भ्यो मन्त्रपतिभ्यो मा मामृषयो मन्त्रकृतो मन्त्रपतयः परादुर्माऽहमृषीन्मन्त्रकृतो मन्त्रपतीन

### TA 5 — Anuvāka 1 (SL `1` unit(s) vs ITX `7` unit(s))
- **SL (unaccented view):** देवा वै सत्रम् आसत । ऋद्धिपरिमितं यशस्कामाः । ते ऽब्रुवन् । यन् नः प्रथमं यश ऋच्छात् । सर्वेषां नस् तत् सहासद् इति । तेषां कुरुक्षेत्रं वेदिर् आसीत् । तस्यै खाण्डवो दक्षिणार्ध आसीत
- **ITX (unaccented view):** देवा वै सत्रमासत । ऋद्धिपरिमितं यशस्कामाः । तेऽब्रुवन् । यन्नः प्रथमं यश ऋच्छात् । सर्वेषां नस्तथ्सहासदिति । तेषां कुरुक्षेत्रं वेदिरासीत् । तस्यै खाण्डवो दक्षिणार्ध आसीत् । तूर्घ्

### TA 7 — Anuvāka 1 (SL `1` unit(s) vs ITX `1` unit(s))
- **SL (unaccented view):** ओं शं नो मित्रः शं वरुणः । शं नो भवत्वर्यमा । शं न इन्द्रो बृहस्पतिः । शं नो विष्णुरुरुक्रमः । नमो ब्रह्मणे । नमस्ते वायो । त्वमेव प्रत्यक्षं ब्रह्मासि । त्वामेवप्रत्यक्षं ब्रह्म व
- **ITX (unaccented view):** शं नो मित्रः शं वरुणः । शं नो भवत्वर्यमा । शं न इन्द्रो बृहस्पतिः । शं नो विष्णुरुरुक्रमः । नमो ब्रह्मणे । नमस्ते वायो । त्वमेव प्रत्यक्षं ब्रह्मासि । त्वमेव प्रत्यक्षं ब्रह्म वदिष

### TA 8 — Anuvāka 1 (SL `1` unit(s) vs ITX `1` unit(s))
- **SL (unaccented view):** ओं सह नाववतु । सह नौ भुनक्तु । सह वीर्यं करवावहै । तेजस्वि नावधीतमस्तु मा विद्विषावहै । ओं शान्तिः शान्तिः शान्तिः । ओं ब्रह्मविदाप्नोति परम् । तदेषा ऽभुक्ता । सत्यं ज्ञानमनन्तं ब्
- **ITX (unaccented view):** ब्रह्मविदाप्नोति परम् । तदेषाऽभ्युक्ता । सत्यं ज्ञानमनन्तं ब्रह्म । यो वेद निहितं गुहायां परमे व्योमन्न् । सोऽश्नुते सर्वान्कामान्थ्सह । ब्रह्मणा विपश्चितेति । तस्माद्वा एतस्मादात्

### TA 9 — Anuvāka 1 (SL `1` unit(s) vs ITX `1` unit(s))
- **SL (unaccented view):** ओं सह नाववतु । सह नौ भुनक्तु । सह वीर्यं करवावहै । तेजस्वि नावधीतमस्तु मा विद्विषावहै । ओं शान्तिः शान्तिः शान्तिः । भृगुर्वै वारुणिः । वरुणं पितरमुपससार । अधीहि भगवो ब्रह्मेति । त
- **ITX (unaccented view):** भृगुर्वै वारुणिः । वरुणं पितरमुपससार । अधीहि भगवो ब्रह्मेति । तस्मा एतत्प्रोवाच । अन्नं प्राणं चक्षुः श्रोत्रं मनो वाचमिति । तं होवाच । यतो वा इमानि भूतानि जायन्ते । येन जातानि जीव

