# Library sources and licenses

The library is plain-text copies of the sources below, converted with `library/build_library.py`.
Each source keeps its own license, and the app shows it with every article. Text from Creative Commons
sources is shared under the same license (ShareAlike), credited to its authors: each article keeps its
source address, Stack Exchange posts and iFixit guides keep their authors' names, and this file travels
inside every library download. Licenses and terms were checked on 2026-10-24.

"Essentials" is the smaller download (1.3 GB); "Everything" adds Wikipedia and iFixit.

## In the library downloads

| Source | What it covers | License | In | Where it comes from |
|---|---|---|---|---|
| Wikipedia, about 930,000 of the most-read articles | General knowledge | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), Wikipedia contributors | Everything | Kiwix `wikipedia_en_top1m` |
| WikiMed | Medical encyclopedia (Wikipedia medicine) | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), Wikipedia contributors | Both | Kiwix `wikipedia_en_medicine` |
| WikEM | Emergency medicine | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), WikEM contributors | Both | Kiwix `wikem_en_all` |
| MedlinePlus (NLM-written pages only) | Health topics, lab tests, genetics | Public domain (U.S. National Library of Medicine) | Both | Kiwix `medlineplus.gov_en_all`; licensed sections removed (see below) |
| UK Medicines A to Z | How to take common medicines safely | Contains public sector information licensed under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/). A static copy of the nhs.uk medicines pages as of September 2026; under the NHS website's terms it is not presented as the NHS website. | Both | Kiwix `nhs.uk_en_medicines` |
| CDC Travelers' Health | Disease, water and food safety | Public domain (CDC). Includes the online CDC Yellow Book; its printed edition is published by Oxford University Press. | Both | Kiwix `wwwnc.cdc.gov_en_all` |
| Ready.gov (FEMA) | Emergency preparedness by hazard | Public domain (FEMA) | Both | Kiwix `ready.gov_en_all` |
| Military medicine manuals | Hospital Corpsman, First Aid (FM 4-25.11), Ship's Medicine Chest, field sanitation, preventive medicine, radiation protection | Public domain (U.S. government). Three volumes that reprint copyrighted material (Military Dermatology, War Psychiatry, FM 21-11) are left out. | Both | Kiwix `irp.fas.org_en_military-medicine` |
| U.S. government survival and first-aid manuals | USAF AFH 10-644 SERE Operations, Army ATP 3-50.21 Survival, ATP 4-02.11 First Aid (2026), TC 21-3 Cold Weather, ATP 4-25.12 Field Sanitation, TB MED 577 Field Water, TB MED 507 Heat, FEMA Are You Ready?, FEMA CERT manual, Joint Trauma System Prolonged Casualty Care | Public domain (17 U.S.C. 105) | Both | `library/fetch_manuals.py` |
| Nuclear War Survival Skills (Cresson Kearny, ORNL, 1979; 1987 edition) | Fallout shelter, water, ventilation | Oak Ridge National Laboratory report; the 1986 additions are copyright Cresson H. Kearny, reproduced with his notice, which is kept in the text | Both | `library/fetch_manuals.py` |
| Emergency Response Guidebook 2024 | Hazardous materials spills and fires | Reproduction permitted without further permission by the participating governments (U.S. DOT/PHMSA, Transport Canada, Mexico's SICT, Argentina's CIQUIME); not for resale | Both | `library/fetch_manuals.py` (from the Internet Archive; the official site refuses scripted downloads) |
| Risk and micromort references | Estimating risks of death: the Social Security life table (2023) restated in micromorts per year and per day, CDC's "Mortality in the United States, 2024" and "Deaths: Leading Causes for 2024", NHTSA's 2024 crash overview (deaths per mile driven), the National Weather Service's lightning odds; plus, in Essentials only, Wikipedia's articles on micromorts, Fermi estimates, life tables, relative risk and related topics | Government statistics: public domain (SSA, CDC, NHTSA, NWS). Wikipedia articles: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) | Both | `library/fetch_risk.py` (CDC and SSA files from the Internet Archive; their sites refuse scripted downloads) |
| USDA Complete Guide to Home Canning (2015) | Safe canning, botulism prevention | Public domain (USDA) | Both | Kiwix `usda-2015_en` |
| wikiHow (2018 text dump) | How-to guides | [CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/) (non-commercial), wikiHow contributors | Both | Hugging Face `Lajvi/wikihowAll` (Koupaee and Wang, 2018) |
| iFixit | Repair guides, with each guide's author | [CC BY-NC-SA 3.0](https://creativecommons.org/licenses/by-nc-sa/3.0/) (non-commercial) | Everything | Kiwix `ifixit_en_all` |
| Appropedia | Appropriate technology, sustainability | [CC BY-SA](https://creativecommons.org/licenses/by-sa/4.0/) 3.0 or 4.0 (per page) | Both | Kiwix `appropedia_en_all` |
| Energypedia | Solar, batteries, cookstoves, biogas | [CC BY-SA](https://creativecommons.org/licenses/by-sa/4.0/) 3.0 or 4.0 (per page) | Both | Kiwix `energypedia_en_all` |
| WikiCiv | Rebuilding technology from scratch | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) | Both | Kiwix `wikiciv_en_all` |
| Stack Exchange: Home Improvement, The Great Outdoors, Seasoned Advice (cooking), Gardening, Lifehacks, Sustainable Living, Amateur Radio, Medical Sciences, Motor Vehicle Repair, Pets | Practical Q&A, with each post's author | CC BY-SA 2.5, 3.0 or 4.0 by post date ([Stack Exchange licensing](https://stackoverflow.com/help/licensing)) | Both | Kiwix Stack Exchange ZIMs |
| IFRC International First Aid, Resuscitation and Education Guidelines 2020 | Evidence-based first aid | © IFRC; copying allowed for non-commercial use with acknowledgement | Both | `library/fetch_manuals.py` |
| WHO-ICRC Basic Emergency Care; WHO Managing Complications in Pregnancy and Childbirth; WHO Guidelines for Drinking-water Quality | Emergency care, childbirth, safe water | [CC BY-NC-SA 3.0 IGO](https://creativecommons.org/licenses/by-nc-sa/3.0/igo/) (non-commercial). WHO does not endorse this app. | Both | `library/fetch_manuals.py` |

Non-commercial sources (wikiHow, iFixit, IFRC, WHO) are fine for this free project. Anyone who
wants to use the library commercially should rebuild it without them.

## Left out on purpose

- The Agorisme wiki ([agorismewiki.nl](https://agorismewiki.nl), Dutch: self-sufficiency, food storage, water, energy,
  local economy), from its public repository (`library/fetch_agorismewiki.py`). The site and repository state no
  license (checked 2026-11-07), so it is for personal builds only and never in `--public` or `--lite` packs, until its
  authors give permission. Add it to your own library from the app's Library window (Extra sources), or with `fetch_agorismewiki.py --install`.

- MedlinePlus sections licensed to NLM by third parties: the A.D.A.M. Medical Encyclopedia
  (`/ency/`), ASHP drug information (`/druginfo/meds/`) and Natural Medicines (`/druginfo/natural/`).
  A default (personal) build includes them; `--public` and `--lite` builds, the only ones that are shared,
  leave them out.
- Kiwix "zimgit" collections (post-disaster, water, food, medicine, knots): they bundle PDFs from
  many publishers with mixed rights. Personal builds only, until each document is checked.
- Military Dermatology and War Psychiatry (Textbook of Military Medicine) and FM 21-11 (1988): they reprint
  copyrighted figures and text. FM 4-25.11, which replaced FM 21-11, is included.
- Hesperian books (*Where There Is No Doctor* and others): digital use needs written permission.
- MSF clinical guidelines, the Sphere Handbook, the USAMRIID Blue Book, Red Cross manuals and
  commercial survival books: all rights reserved.
