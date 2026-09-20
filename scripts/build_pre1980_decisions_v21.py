#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v21 (2026-09-19): pre-1980 FDA decision tables extended 1976 -> 1965.

Supersedes ``build_pre1980_decisions_v19.py`` as the single writer of the four
pre-1980 tables.  The v19 treatment of 1977/1978/1979 is reproduced verbatim
(same rows, same note wording) and twelve more years are added, one year at a
time, in the same fail-closed style:

* data/pre1980_fda_decisions.csv          (173 verified Type 1/1-4 rows)
* data/pre1980_year_audit.csv             (15 year rows, official-series verdicts)
* data/pre1980_era_analysis.csv           (15 era rows)
* data/pre1980_primary_captures_index.csv (12 v19 + 11 v21 live captures)
* data/missing_nme_candidates.csv         (NEW: named gap candidates + mechanism)

Verification layers behind every new row (no hallucinations by construction):

1. **Payload integrity.** Regulatory facts are copied verbatim from the
   committed openFDA Drugs@FDA extracts. Every payload file's SHA-256 must
   match its manifest entry, and for 1975-1979 the run-18/run-19 dual-run
   raw_sha256 agreement is re-checked (two independent API fetches ~2h apart).
2. **Live per-row probes.** ``data/raw/pre1980_row_probes_1965_1976/`` carries
   one complete current openFDA record per new decision row (125 applications
   + 1 explicit gap-candidate probe), each SHA-manifested. Date, class,
   priority and holder are compared with the payload; ANY disagreement aborts.
3. **Live year populations.** ``data/raw/pre1980_year_populations_1965_1976/``
   re-queries each year's ORIG/AP population (``limit=1`` -> meta.results.total,
   the documented workaround for count= over nested submission fields).
4. **First-appearance screen** across the 1939-1979 payload universe (the
   1939-1964 block is fetched in this same session so a molecule marketed
   before 1965 can be detected). Every hit must appear in the explicit
   ``ALLOWED_EARLIER`` adjudication table below or the build aborts.
5. **Display names** come from an explicit per-application map; the builder
   aborts if the payload's brand/ingredient strings drift from it.
6. **Official counts** are read from data/fda_official_year_series.csv and
   pinned per year against values re-read live from FDA's history page.

Never asserted: applicant lineage, ticker, indication, or an approval-era
trade name. Sponsors are Drugs@FDA holders of record (qualified as such) and
brand names are the names Drugs@FDA publishes today.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
BLOCKS = {
    (1965, 1969): "openfda_orig_decisions_1965_1969",
    (1970, 1974): "openfda_orig_decisions_1970_1974",
    (1975, 1979): "openfda_orig_decisions_1975_1979",
}
PRE1965_BLOCK = "openfda_orig_decisions_1939_1964"
CAPTURES_DIR = DATA / "raw" / "source_captures_2026_09_19"
EVIDENCE_V19 = CAPTURES_DIR / "live_primary_captures_v19_2026_09_19.json"
EVIDENCE_V21 = CAPTURES_DIR / "live_primary_captures_v21_2026_09_19.json"
RUN18_MANIFEST = CAPTURES_DIR / "run18_manifest_openfda_orig_decisions_1975_1979.json"
PROBES_DIR = DATA / "raw" / "pre1980_row_probes_1965_1976"
POPS_DIR = DATA / "raw" / "pre1980_year_populations_1965_1976"

YEARS = tuple(range(1965, 1980))
NEW_YEARS = tuple(range(1965, 1977))          # added by v21
V19_YEARS = (1977, 1978, 1979)                # built by v19, reproduced verbatim

# Payload NME-comparable (TYPE 1 + TYPE 1/4) counts, recomputed from the
# committed payloads and pinned here so any payload drift aborts the build.
EXPECTED_T1 = {1965: 11, 1966: 7, 1967: 13, 1968: 4, 1969: 8, 1970: 11,
               1971: 7, 1972: 7, 1973: 11, 1974: 16, 1975: 9, 1976: 21,
               1977: 17, 1978: 18, 1979: 13}
EXPECTED_ORIG_AP = {1965: 32, 1966: 16, 1967: 32, 1968: 22, 1969: 25, 1970: 38,
                    1971: 48, 1972: 29, 1973: 43, 1974: 73, 1975: 39, 1976: 80,
                    1977: 42, 1978: 66, 1979: 62}
# (nmes_approved, ndas_approved) re-read live from
# https://www.fda.gov/about-fda/histories-fda-regulated-products/summary-nda-approvals-receipts-1938-present
# on 2026-09-19 (capture V21-C08) and equal to data/fda_official_year_series.csv.
EXPECTED_OFFICIAL = {1965: ("18", "53"), 1966: ("10", "40"), 1967: ("16", "189"),
                     1968: ("14", "59"), 1969: ("5", "38"), 1970: ("15", "51"),
                     1971: ("12", "26"), 1972: ("10", "57"), 1973: ("14", "50"),
                     1974: ("21", "85"), 1975: ("20", "71"), 1976: ("22", "72"),
                     1977: ("25", "63"), 1978: ("17", "86"), 1979: ("14", "94")}
# Live ORIG/AP population totals (meta.results.total, limit=1 queries).
EXPECTED_POPULATION = {1965: 52, 1970: 74, 1976: 619,   # sandbox captures V21-C01..C03
                       1977: 662, 1978: 756, 1979: 746}  # v19 captures V19-C01..C03

DRUGSFDA = ("https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm"
            "?event=overview.process&varApplNo={num}")
OPENFDA_Q = 'https://api.fda.gov/drug/drugsfda.json?search=application_number:%22{appl}%22'

# ---------------------------------------------------------------------------
# Explicit display map: application -> (brand display, generic display,
# expected payload brand_name, expected payload active-ingredient prefix).
# The builder selects the payload product whose brand_name equals the third
# field and whose active_ingredients contain the fourth (see pick_product for
# the disambiguation rule) and aborts on any drift.  Brand/generic strings are
# display renderings of payload values; the payload strings themselves are
# what get asserted.
# ---------------------------------------------------------------------------
DISPLAY = {
    # ---------------- 1965 (11) ----------------
    "NDA014602": ("Celestone Soluspan", "betamethasone acetate and betamethasone sodium phosphate",
                  "CELESTONE SOLUSPAN", "BETAMETHASONE ACETATE"),
    "NDA013026": ("Trecator", "ethionamide", "TRECATOR", "ETHIONAMIDE"),
    "BLA101995": ("Santyl", "collagenase", "SANTYL", "COLLAGENASE"),
    "NDA015539": ("Serax", "oxazepam", "SERAX", "OXAZEPAM"),
    "NDA016059": ("Indocin", "indomethacin", "INDOCIN", "INDOMETHACIN"),
    "NDA014879": ("Dopram", "doxapram hydrochloride", "DOPRAM", "DOXAPRAM HYDROCHLORIDE"),
    "NDA012715": ("Gantanol-DS", "sulfamethoxazole", "GANTANOL-DS", "SULFAMETHOXAZOLE"),
    "NDA012806": ("Cordran", "flurandrenolide", "CORDRAN", "FLURANDRENOLIDE"),
    "NDA014763": ("Citanest Plain", "prilocaine hydrochloride", "CITANEST PLAIN", "PRILOCAINE HYDROCHLORIDE"),
    "NDA012665": ("Velban", "vinblastine sulfate", "VELBAN", "VINBLASTINE SULFATE"),
    "NDA013025": ("THAM", "tromethamine", "THAM", "TROMETHAMINE"),
    # ---------------- 1966 (7) ----------------
    "NDA012429": ("Thioguanine", "thioguanine", "THIOGUANINE", "THIOGUANINE"),
    "NDA016029": ("Ovulen-21", "ethynodiol diacetate and mestranol", "OVULEN-21", "ETHYNODIOL DIACETATE"),
    "NDA016000": ("Sulla", "sulfameter", "SULLA", "SULFAMETER"),
    "NDA016245": ("Vercyte", "pipobroman", "VERCYTE", "PIPOBROMAN"),
    "NDA016273": ("Lasix", "furosemide", "LASIX", "FUROSEMIDE"),
    "NDA015500": ("Tolinase", "tolazamide", "TOLINASE", "TOLAZAMIDE"),
    "NDA016084": ("Zyloprim", "allopurinol", "ZYLOPRIM", "ALLOPURINOL"),
    # ---------------- 1967 (13) ----------------
    "NDA016092": ("Edecrin", "ethacrynic acid", "EDECRIN", "ETHACRYNIC ACID"),
    "NDA016131": ("Clomid", "clomiphene citrate", "CLOMID", "CLOMIPHENE CITRATE"),
    "NDA016099": ("Atromid-S", "clofibrate", "ATROMID-S", "CLOFIBRATE"),
    "NDA015034": ("Ponstel", "mefenamic acid", "PONSTEL", "MEFENAMIC ACID"),
    "NDA016033": ("Vontrol", "diphenidol hydrochloride", "VONTROL", "DIPHENIDOL HYDROCHLORIDE"),
    "NDA016096": ("Mintezol", "thiabendazole", "MINTEZOL", "THIABENDAZOLE"),
    "NDA015921": ("Haldol", "haloperidol", "HALDOL", "HALOPERIDOL"),
    "NDA016194": ("Talwin", "pentazocine lactate", "TALWIN", "PENTAZOCINE LACTATE"),
    "NDA016584": ("Navane", "thiothixene", "NAVANE", "THIOTHIXENE"),
    "NDA016012": ("Vivactil", "protriptyline hydrochloride", "VIVACTIL", "PROTRIPTYLINE HYDROCHLORIDE"),
    "NDA016320": ("Myambutol", "ethambutol hydrochloride", "MYAMBUTOL", "ETHAMBUTOL HYDROCHLORIDE"),
    "NDA016418": ("Inderal", "propranolol hydrochloride", "INDERAL", "PROPRANOLOL HYDROCHLORIDE"),
    "NDA016295": ("Droxia", "hydroxyurea", "DROXIA", "HYDROXYUREA"),
    # ---------------- 1968 (4) ----------------
    "NDA016608": ("Tegretol", "carbamazepine", "TEGRETOL", "CARBAMAZEPINE"),
    "NDA016324": ("Imuran", "azathioprine", "IMURAN", "AZATHIOPRINE"),
    "NDA016267": ("Desferal", "deferoxamine mesylate", "DESFERAL", "DEFEROXAMINE MESYLATE"),
    "NDA016672": ("Ovral", "ethinyl estradiol and norgestrel", "OVRAL", "ETHINYL ESTRADIOL"),
    # ---------------- 1969 (8) ----------------
    "NDA013615": ("Quide", "piperacetazine", "QUIDE", "PIPERACETAZINE"),
    "NDA016119": ("Teslac", "testolactone", "TESLAC", "TESTOLACTONE"),
    "NDA012828": ("Travase", "sutilains", "TRAVASE", "SUTILAINS"),
    "NDA016793": ("Cytarabine", "cytarabine", "CYTARABINE", "CYTARABINE"),
    "NDA016785": ("Matulane", "procarbazine hydrochloride", "MATULANE", "PROCARBAZINE HYDROCHLORIDE"),
    "NDA016798": ("Sinequan", "doxepin hydrochloride", "SINEQUAN", "DOXEPIN HYDROCHLORIDE"),
    "NDA013731": ("Bilopaque", "tyropanoate sodium", "BILOPAQUE", "TYROPANOATE SODIUM"),
    "NDA016624": ("HMS", "medryone", "HMS", "MEDRYSONE"),
    # ---------------- 1970 (11) ----------------
    "NDA016769": ("Urispas", "flavoxate hydrochloride", "URISPAS", "FLAVOXATE HYDROCHLORIDE"),
    "NDA016812": ("Ketalar", "ketamine hydrochloride", "KETALAR", "KETAMINE HYDROCHLORIDE"),
    "NDA016774": ("Serentil", "mesoridazine besylate", "SERENTIL", "MESORIDAZINE BESYLATE"),
    "NDA016782": ("Lithonate", "lithium carbonate", "LITHONATE", "LITHIUM CARBONATE"),
    "NDA016721": ("Dalmane", "flurazepam hydrochloride", "DALMANE", "FLURAZEPAM HYDROCHLORIDE"),
    "NDA016750": ("Cortrosyn", "cosyntropin", "CORTROSYN", "COSYNTROPIN"),
    "NDA050109": ("Mithracin", "plicamycin", "MITHRACIN", "PLICAMYCIN"),
    "NDA016912": ("Larodopa", "levodopa", "LARODOPA", "LEVODOPA"),
    "NDA016885": ("Lysodren", "mitotane", "LYSODREN", "MITOTANE"),
    "NDA019853": ("Cuprimine", "penicillamine", "CUPRIMINE", "PENICILLAMINE"),
    "NDA016929": ("FUDR", "floxuridine", "FUDR", "FLOXURIDINE"),
    # ---------------- 1971 (7) ----------------
    "NDA016636": ("Narcan", "naloxone hydrochloride", "NARCAN", "NALOXONE HYDROCHLORIDE"),
    "NDA016908": ("Lidex", "fluocinonide", "LIDEX", "FLUOCINONIDE"),
    "NDA016942": ("Halotex", "haloprogin", "HALOTEX", "HALOPROGIN"),
    "NDA016979": ("Megace", "megestrol acetate", "MEGACE", "MEGESTROL ACETATE"),
    "NDA016921": ("Retin-A", "tretinoin", "RETIN-A", "TRETINOIN"),
    "NDA016224": ("Robengatope", "rose bengal sodium I-131", "ROBENGATOPE", "ROSE BENGAL SODIUM I-131"),
    "NDA017001": ("Ancobon", "flucytosine", "ANCOBON", "FLUCYTOSINE"),
    # ---------------- 1972 (7) ----------------
    "NDA017010": ("Desonide", "desonide", "DESONIDE", "DESONIDE"),
    "NDA017042": ("Fluorine F-18", "sodium fluoride F-18", "FLUORINE F-18", "SODIUM FLUORIDE F-18"),
    "NDA017105": ("Tranxene", "clorazepate dipotassium", "TRANXENE", "CLORAZEPATE DIPOTASSIUM"),
    "NDA017087": ("Ethrane", "enflurane", "ETHRANE", "ENFLURANE"),
    "NDA016968": ("Miostat", "carbachol", "MIOSTAT", "CARBACHOL"),
    "NDA016964": ("Marcaine hydrochloride", "bupivacaine hydrochloride",
                  "MARCAINE HYDROCHLORIDE", "BUPIVACAINE HYDROCHLORIDE"),
    "NDA017015": ("Pavulon", "pancuronium bromide", "PAVULON", "PANCURONIUM BROMIDE"),
    # ---------------- 1973 (11) ----------------
    "NDA016996": ("Hyperstat", "diazoxide", "HYPERSTAT", "DIAZOXIDE"),
    "NDA017047": ("Sethotope", "selenomethionine Se-75", "SETHOTOPE", "SELENOMETHIONINE SE-75"),
    "NDA017129": ("Cholebrine", "iocetamic acid", "CHOLEBRINE", "IOCETAMIC ACID"),
    "NDA017247": ("Sanorex", "mazindol", "SANOREX", "MAZINDOL"),
    "NDA017376": ("Septra", "sulfamethoxazole and trimethoprim", "SEPTRA", "SULFAMETHOXAZOLE"),
    "NDA016402": ("Alupent", "metaproterenol sulfate", "ALUPENT", "METAPROTERENOL SULFATE"),
    "NDA050443": ("Blenoxane", "bleomycin sulfate", "BLENOXANE", "BLEOMYCIN SULFATE"),
    "NDA017454": ("Osteoscan", "technetium Tc-99m etidronate", "OSTEOSCAN", "TECHNETIUM TC-99M ETIDRONATE"),
    "NDA016211": ("Miochol", "acetylcholine chloride", "MIOCHOL", "ACETYLCHOLINE CHLORIDE"),
    "NDA017386": ("Zaroxolyn", "metolazone", "ZAROXOLYN", "METOLAZONE"),
    "NDA016729": ("Ferrous citrate Fe 59", "ferrous citrate Fe-59", "FERROUS CITRATE FE 59", "FERROUS CITRATE"),
    # ---------------- 1974 (16) ----------------
    "NDA017443": ("Dantrium", "dantrolene sodium", "DANTRIUM", "DANTROLENE SODIUM"),
    "NDA017111": ("Moban", "molindone hydrochloride", "MOBAN", "MOLINDONE HYDROCHLORIDE"),
    "NDA050459": ("Amoxil", "amoxicillin", "AMOXIL", "AMOXICILLIN"),
    "NDA017450": ("Monistat 7", "miconazole nitrate", "MONISTAT 7", "MICONAZOLE NITRATE"),
    "NDA017395": ("Intropin", "dopamine hydrochloride", "INTROPIN", "DOPAMINE HYDROCHLORIDE"),
    "NDA016820": ("Emete-Con", "benzquinamide hydrochloride", "EMETE-CON", "BENZQUINAMIDE HYDROCHLORIDE"),
    "NDA017466": ("Bricanyl", "terbutaline sulfate", "BRICANYL", "TERBUTALINE SULFATE"),
    "NDA017546": ("Nipride", "sodium nitroprusside", "NIPRIDE", "SODIUM NITROPRUSSIDE"),
    "NDA017481": ("Vermox", "mebendazole", "VERMOX", "MEBENDAZOLE"),
    "BLA050114": ("Pre-Pen", "benzylpenicilloyl polylysine", "PRE-PEN", "BENZYLPENICILLOYL POLYLYSINE"),
    "NDA017048": ("Peptavlon", "pentagastrin", "PEPTAVLON", "PENTAGASTRIN"),
    "NDA050467": ("Doxorubicin hydrochloride", "doxorubicin hydrochloride",
                  "DOXORUBICIN HYDROCHLORIDE", "DOXORUBICIN HYDROCHLORIDE"),
    "NDA017503": ("Combipres", "chlorthalidone and clonidine hydrochloride", "COMBIPRES", "CHLORTHALIDONE"),
    "NDA017463": ("Motrin", "ibuprofen", "MOTRIN", "IBUPROFEN"),
    "NDA017551": ("Perchloracap", "potassium perchlorate", "PERCHLORACAP", "POTASSIUM PERCHLORATE"),
    "NDA017556": ("Halog", "halcinonide", "HALOG", "HALCINONIDE"),
    # ---------------- 1975 (9) ----------------
    "NDA016832": ("Cylert", "pemoline", "CYLERT", "PEMOLINE"),
    "NDA017613": ("Lotrimin", "clotrimazole", "LOTRIMIN", "CLOTRIMAZOLE"),
    "NDA017525": ("Loxitane", "loxapine succinate", "LOXITANE", "LOXAPINE SUCCINATE"),
    "NDA017555": ("Sinemet", "carbidopa and levodopa", "SINEMET", "CARBIDOPA"),
    "NDA017575": ("DTIC-Dome", "dacarbazine", "DTIC-DOME", "DACARBAZINE"),
    "NDA017533": ("Klonopin", "clonazepam", "KLONOPIN", "CLONAZEPAM"),
    "NDA050477": ("Nebcin", "tobramycin sulfate", "NEBCIN", "TOBRAMYCIN SULFATE"),
    "NDA017577": ("Ditropan", "oxybutynin chloride", "DITROPAN", "OXYBUTYNIN CHLORIDE"),
    "NDA017569": ("Renoquid", "sulfacytine", "RENOQUID", "SULFACYTINE"),
    # ---------------- 1976 (21) ----------------
    "BLA017835": ("Chromalbin", "albumin chromated Cr-51 serum", "CHROMALBIN", "ALBUMIN CHROMATED CR-51 SERUM"),
    "BLA017836": ("Jeanatope", "albumin iodinated I-125 serum", "JEANATOPE", "ALBUMIN IODINATED I-125 SERUM"),
    "NDA017518": ("Ytterbium Yb 169 DTPA", "pentetate calcium trisodium Yb-169",
                  "YTTERBIUM YB 169 DTPA", "PENTETATE CALCIUM TRISODIUM YB-169"),
    "NDA017581": ("Naprosyn", "naproxen", "NAPROSYN", "NAPROXEN"),
    "NDA017604": ("Nalfon", "fenoprofen calcium", "NALFON", "FENOPROFEN CALCIUM"),
    "NDA017628": ("Tolectin 600", "tolmetin sodium", "TOLECTIN 600", "TOLMETIN SODIUM"),
    "NDA017630": ("Sodium iodide I 123", "sodium iodide I-123", "SODIUM IODIDE I 123", "SODIUM IODIDE I-123"),
    "NDA017657": ("Cephulac", "lactulose", "CEPHULAC", "LACTULOSE"),
    "NDA017573": ("Vanceril", "beclomethasone dipropionate", "VANCERIL", "BECLOMETHASONE DIPROPIONATE"),
    "NDA017478": ("Gallium citrate Ga 67", "gallium citrate Ga-67", "GALLIUM CITRATE GA 67", "GALLIUM CITRATE GA-67"),
    "NDA017557": ("Danocrine", "danazol", "DANOCRINE", "DANAZOL"),
    "NDA017442": ("Minipress", "prazosin hydrochloride", "MINIPRESS", "PRAZOSIN HYDROCHLORIDE"),
    "NDA017697": ("Kinevac", "sincalide", "KINEVAC", "SINCALIDE"),
    "NDA017588": ("Gleostine", "lomustine", "GLEOSTINE", "LOMUSTINE"),
    "NDA017751": ("Duranest", "etidocaine hydrochloride", "DURANEST", "ETIDOCAINE HYDROCHLORIDE"),
    "NDA017594": ("Capitrol", "chloroxine", "CAPITROL", "CHLOROXINE"),
    "NDA017638": ("Thypinone", "protirelin", "THYPINONE", "PROTIRELIN"),
    "NDA050497": ("Ticar", "ticarcillin disodium", "TICAR", "TICARCILLIN DISODIUM"),
    "NDA017869": ("Funduscein-25", "fluorescein sodium", "FUNDUSCEIN-25", "FLUORESCEIN SODIUM"),
    "NDA050486": ("Vira-A", "vidarabine", "VIRA-A", "VIDARABINE"),
    "NDA017694": ("Imodium", "loperamide hydrochloride", "IMODIUM", "LOPERAMIDE HYDROCHLORIDE"),
    # ---------------- 1977 (17, v19) ----------------
    "NDA017535": ("Lorelco", "probucol", "LORELCO", "PROBUCOL"),
    "NDA017661": ("Tavist-1", "clemastine fumarate", "TAVIST-1", "CLEMASTINE FUMARATE"),
    "NDA017856": ("Topicort", "desoximetasone", "TOPICORT", "DESOXIMETASONE"),
    "NDA017422": ("Bicnu", "carmustine", "BICNU", "CARMUSTINE"),
    "NDA017601": ("Optimine", "azatadine maleate", "OPTIMINE", "AZATADINE MALEATE"),
    "NDA017563": ("Colestid", "colestipol hydrochloride", "COLESTID", "COLESTIPOL HYDROCHLORIDE"),
    "NDA017920": ("Tagamet", "cimetidine", "TAGAMET", "CIMETIDINE"),
    "NDA017765": ("Cloderm", "clocortolone pivalate", "CLODERM", "CLOCORTOLONE PIVALATE"),
    "NDA017810": ("Prostin E2", "dinoprostone", "PROSTIN E2", "DINOPROSTONE"),
    "NDA017821": ("Flexeril", "cyclobenzaprine hydrochloride", "FLEXERIL", "CYCLOBENZAPRINE HYDROCHLORIDE"),
    "NDA017447": ("Norpace", "disopyramide phosphate", "NORPACE", "DISOPYRAMIDE PHOSPHATE"),
    "NDA017831": ("Didronel", "etidronate disodium", "DIDRONEL", "ETIDRONATE DISODIUM"),
    "NDA017741": ("Florone", "diflorasone diacetate", "FLORONE", "DIFLORASONE DIACETATE"),
    "NDA017794": ("Ativan", "lorazepam", "ATIVAN", "LORAZEPAM"),
    "NDA017851": ("Lioresal", "baclofen", "LIORESAL", "BACLOFEN"),
    "NDA017806": ("Thallous Chloride Tl 201", "thallous chloride Tl-201",
                  "THALLOUS CHLORIDE TL 201", "THALLOUS CHLORIDE"),
    "NDA017970": ("Nolvadex", "tamoxifen citrate", "NOLVADEX", "TAMOXIFEN CITRATE"),
    # ---------------- 1978 (18, v19) ----------------
    "BLA101063": ("Elspar", "asparaginase", "ELSPAR", "ASPARAGINASE"),
    "NDA050512": ("Duricef", "cefadroxil", "DURICEF", "CEFADROXIL"),
    "NDA017922": ("DDAVP", "desmopressin acetate", "DDAVP", "DESMOPRESSIN ACETATE"),
    "NDA018081": ("Depakene", "valproic acid", "DEPAKENE", "VALPROIC ACID"),
    "NDA017788": ("Rimso-50", "dimethyl sulfoxide", "RIMSO-50", "DIMETHYL SULFOXIDE"),
    "NDA017907": ("Glucoscan", "technetium Tc-99m gluceptate", "GLUCOSCAN", "TECHNETIUM TC-99M GLUCEPTATE"),
    "NDA017962": ("Parlodel", "bromocriptine mesylate", "PARLODEL", "BROMOCRIPTINE MESYLATE"),
    "NDA017744": ("Motofen", "difenoxin hydrochloride and atropine sulfate", "MOTOFEN", "DIFENOXIN"),
    "NDA017820": ("Dobutrex", "dobutamine hydrochloride", "DOBUTREX", "DOBUTAMINE"),
    "NDA017963": ("Lopressor", "metoprolol tartrate", "LOPRESSOR", "METOPROLOL TARTRATE"),
    "NDA018044": ("Rocaltrol", "calcitriol", "ROCALTROL", "CALCITRIOL"),
    "NDA018086": ("Timoptic", "timolol maleate", "TIMOPTIC", "TIMOLOL MALEATE"),
    "NDA017857": ("Stadol", "butorphanol tartrate", "STADOL", "BUTORPHANOL TARTRATE"),
    "NDA017982": ("Amipaque", "metrizamide", "AMIPAQUE", "METRIZAMIDE"),
    "NDA017911": ("Clinoril", "sulindac", "CLINORIL", "SULINDAC"),
    "NDA050504": ("Mandol", "cefamandole nafate", "MANDOL", "CEFAMANDOLE"),
    "NDA050517": ("Mefoxin", "cefoxitin sodium", "MEFOXIN", "CEFOXITIN SODIUM"),
    "NDA018057": ("Platinol-AQ", "cisplatin", "PLATINOL-AQ", "CISPLATIN"),
    # ---------------- 1979 (13, v19) ----------------
    "NDA017989": ("Hemabate", "carboprost tromethamine", "HEMABATE", "CARBOPROST TROMETHAMINE"),
    "NDA017862": ("Reglan", "metoclopramide hydrochloride", "REGLAN", "METOCLOPRAMIDE"),
    "NDA050521": ("Ceclor", "cefaclor", "CECLOR", "CEFACLOR"),
    "NDA018024": ("Nubain", "nalbuphine hydrochloride", "NUBAIN", "NALBUPHINE HYDROCHLORIDE"),
    "NDA018203": ("Liposyn 10%", "safflower oil", "LIPOSYN 10%", "SAFFLOWER OIL"),
    "NDA016792": ("Surmontil", "trimipramine maleate", "SURMONTIL", "TRIMIPRAMINE MALEATE"),
    "NDA050508": ("Cyclapen-W", "cyclacillin", "CYCLAPEN-W", "CYCLACILLIN"),
    "NDA017871": ("Demser", "metyrosine", "DEMSER", "METYROSINE"),
    "NDA018116": ("Cyclocort", "amcinonide", "CYCLOCORT", "AMCINONIDE"),
    "NDA018154": ("Loniten", "minoxidil", "LONITEN", "MINOXIDIL"),
    "NDA018063": ("Corgard", "nadolol", "CORGARD", "NADOLOL"),
    "NDA017624": ("Forane", "isoflurane", "FORANE", "ISOFLURANE"),
    "NDA050484": ("Cerubidine", "daunorubicin hydrochloride", "CERUBIDINE", "DAUNORUBICIN"),
}

# ---------------------------------------------------------------------------
# Disambiguation: applications whose brand string covers both a plain product
# and combination products.  The chosen display product must start with this
# exact ingredient string, so the selection is deterministic and auditable.
# ---------------------------------------------------------------------------
PRODUCT_STARTSWITH = {
    "NDA017751": "ETIDOCAINE HYDROCHLORIDE",   # plain etidocaine, not the +epinephrine products
}

# ---------------------------------------------------------------------------
# Adjudicated first-appearance exceptions.  Key: (year, application,
# ingredient) -> reason.  Anything not listed aborts the build, so the list is
# the complete, reviewed record of every "ingredient seen earlier" hit in the
# 1939-1979 payload universe.
# ---------------------------------------------------------------------------
ALLOWED_EARLIER = {
    (1965, "NDA012715", "SULFAMETHOXAZOLE"):
        "Gantanol suspension NDA013664 (TYPE 5 - New Formulation or New Manufacturer, "
        "1965-07-01, ROCHE) precedes the TYPE 1 tablet NDA012715 (1965-08-25) by 55 days; "
        "both live-verified on the Drugs@FDA website (V21-C09/V21-C10). Genuine FDA-data "
        "class/date inversion; sulfamethoxazole counted once via the TYPE 1 row.",
    (1965, "NDA012806", "FLURANDRENOLIDE"):
        "Cordran lotion NDA013790 (TYPE 3 - New Indication or Labeling Change, 1963-03-19, "
        "INA PHARMS) carries the same brand and ingredient and precedes the TYPE 1 Cordran "
        "NDA012806 (1965-10-18) by 27 months - a class/date inversion of the same class as "
        "the Gantanol and Cyclapen findings (an earlier supplemental-class record before the "
        "TYPE 1 record; the payloads publish no parent application for NDA013790). "
        "Flurandrenolide counted once via the TYPE 1 row; the inversion is flagged, not "
        "corrected.",
    (1965, "NDA014763", "EPINEPHRINE BITARTRATE"):
        "Epinephrine bitartrate is a combination component of the Citanest Forte products "
        "within this application, not the new entity (the NME is prilocaine; the display "
        "product is Citanest Plain); it first appears in the payloads on Medihaler-Epi "
        "NDA010374 (1956-03-09, class unpublished by FDA, 3M) and is a pre-1965 marketed "
        "molecule.",
    (1966, "NDA016029", "MESTRANOL"):
        "Ovulen-21 is an FDA-classified TYPE 1/4 (NME + new combination; the NME is "
        "ethynodiol diacetate); mestranol first appears in the payloads on Enovid "
        "NDA010976 (TYPE 1/4, 1961-03-09, GD SEARLE LLC). Combination component, not a "
        "second NME.",
    (1968, "NDA016672", "ETHINYL ESTRADIOL"):
        "Ovral is an FDA-classified TYPE 1/4 (NME + new combination; the NME is norgestrel); "
        "ethinyl estradiol first appears in the payloads on Estinyl NDA005292 (1943-06-25, "
        "class unpublished by FDA, SCHERING). Combination component, not a second NME.",
    (1972, "NDA016964", "EPINEPHRINE BITARTRATE"):
        "Epinephrine bitartrate is a combination component of the Marcaine w/ epinephrine "
        "products, not the new entity; it first appears in the payloads on Medihaler-Epi "
        "NDA010374 (1956-03-09, class unpublished by FDA, 3M) and is a pre-1965 marketed "
        "molecule.",
    (1973, "NDA017376", "SULFAMETHOXAZOLE"):
        "Septra is an FDA-classified TYPE 1/4 (NME + new combination); sulfamethoxazole "
        "first appears in the payloads on Gantanol suspension NDA013664 (TYPE 5, "
        "1965-07-01) and the Gantanol-DS tablets NDA012715 (TYPE 1, 1965-08-25). "
        "Combination component, not a second NME.",
    (1974, "NDA017450", "MICONAZOLE NITRATE"):
        "Monistat-Derm cream NDA017494 (TYPE 5, 1974-01-08, INSIGHT PHARMS) precedes the "
        "TYPE 1 Monistat 7 vaginal cream NDA017450 (1974-01-30) by 22 days - same ingredient, "
        "different application. Miconazole counted once via the TYPE 1 row.",
    (1974, "NDA017503", "CHLORTHALIDONE"):
        "Combipres is an FDA-classified TYPE 1/4 (NME + new combination; the NME is "
        "chlorthalidone); it first appears in the payloads on Hygroton NDA012283 (TYPE 1, "
        "1960-04-07, PRIORITY, SANOFI AVENTIS US). Counted once via this TYPE 1/4 row.",
    (1974, "NDA017503", "CLONIDINE HYDROCHLORIDE"):
        "Combipres is an FDA-classified TYPE 1/4 (NME + new combination); Catapres tablets "
        "NDA017407 (TYPE 3, PRIORITY, BOEHRINGER INGELHEIM) publish clonidine with the same "
        "top-level payload date (1974-09-03) as Combipres. Combination component of the "
        "same-day pairing, not a second NME.",
    (1975, "NDA017555", "LEVODOPA"):
        "Sinemet is an FDA-classified TYPE 1/4 (NME + new combination); levodopa first "
        "appears on Larodopa NDA016912 (TYPE 1, 1970-06-04). Combination component.",
    (1976, "NDA017751", "EPINEPHRINE"):
        "Epinephrine is a combination component of the Duranest w/ epinephrine products; "
        "first appears in the payloads on Xylocaine w/ epinephrine NDA006488 (1948-11-19, "
        "class unpublished by FDA, FRESENIUS KABI USA) and is a pre-1965 marketed molecule. "
        "The row's display product is the plain etidocaine product.",
    (1976, "NDA017751", "EPINEPHRINE BITARTRATE"):
        "Same combination-component condition as EPINEPHRINE on this row; first appears in "
        "the payloads on Medihaler-Epi NDA010374 (1956-03-09, class unpublished by FDA, 3M).",
    (1976, "NDA017694", "LOPERAMIDE HYDROCHLORIDE"):
        "NDA017690 carries the identical product (IMODIUM LOPERAMIDE HYDROCHLORIDE 2MG "
        "CAPSULE ORAL, J AND J CONSUMER INC) with an ORIG-1 of the SAME day (1976-12-28) "
        "classified TYPE 5; live-verified (V21-C11), and FDA's 2016 approval letter covers "
        "both 017690s005 and 017694s052. Duplicate-product condition; loperamide counted "
        "once via the TYPE 1 row.",
    (1978, "NDA017744", "ATROPINE SULFATE"):
        "Motofen is an FDA-classified TYPE 1/4 (NME + new combination; the NME is difenoxin "
        "hydrochloride, verified live V19-C07); atropine sulfate first appears in the "
        "payloads on Lomotil NDA012462 (TYPE 4 - New Combination, 1960-09-15, PRIORITY, "
        "PFIZER) and is a pre-1965 marketed molecule. Combination component, not a second "
        "NME.",
    (1979, "NDA050508", "CYCLACILLIN"):
        "Cyclapen tablet NDA050509 (TYPE 3, 1979-09-13) precedes suspension NDA050508 "
        "(TYPE 1, 1979-09-14) by one day - verified live in both directions in v19 "
        "(V19-C08/V19-C11). Counted once via the TYPE 1 row.",
}

# Live 2026-09-19 evidence attached to individual rows (v19 rows keep v19 text).
LIVE_V19 = {
    "NDA017920": "Live 2026-09-19: openFDA ORIG/AP/exact-date coexistence total=1 (V19-C04) and Drugs@FDA page row '08/16/1977 | ORIG-1 | Approval | Type 1 - New Molecular Entity | PRIORITY' (V19-C10).",
    "NDA017970": "Live 2026-09-19: openFDA ORIG/AP/exact-date coexistence total=1 (V19-C06); ~50 supplements so the ORIG block sits below the first response chunk - precise linkage from the committed full-record extraction.",
    "BLA101063": "Live 2026-09-19: verbatim openFDA ORIG block ORIG-1/AP/19780110/UNKNOWN/TYPE 1, sponsor MERCK, ELSPAR ASPARAGINASE (V19-C05).",
    "NDA017744": "Live 2026-09-19: verbatim openFDA ORIG block ORIG-1/AP/19780714/STANDARD/TYPE 1-4 'Type 1 - New Molecular Entity and Type 4 - New Combination' (V19-C07).",
    "NDA050508": "Live 2026-09-19: verbatim openFDA ORIG block ORIG-1/AP/19790914/STANDARD/TYPE 1, WYETH AYERST, three cyclacillin suspension products (V19-C08). Sibling tablet NDA050509 verified live as ORIG-1/AP/19790913/STANDARD/TYPE 3 (V19-C11) - the class/date inversion is a genuine FDA-data condition; cyclacillin counts once via this row.",
    "NDA017624": "Live 2026-09-19: verbatim openFDA ORIG block ORIG-1/AP/19791218/PRIORITY/TYPE 1 (V19-C09).",
}
LIVE_V21 = {
    "NDA019853": ("Live 2026-09-19: verbatim openFDA ORIG block ORIG-1/AP/19701204/STANDARD/"
                  "TYPE 1 and Drugs@FDA page row '12/04/1970 | ORIG-1 | Approval | Type 1 - New "
                  "Molecular Entity | STANDARD' (V21-C04/V21-C05). IRREGULARITY FLAGGED: "
                  "application number 019853 is out of sequence for a 1970 approval (1970-era "
                  "numbers in this table run 0167xx-0169xx); the date is confirmed on both FDA "
                  "surfaces, so the row is published as FDA carries it and the numbering "
                  "anomaly is flagged for review, not corrected (same class as the open "
                  "NDA022046 lineage artifact)."),
    "NDA012715": ("Live 2026-09-19: Drugs@FDA page row '08/25/1965 | ORIG-1 | Approval | Type 1 - "
                  "New Molecular Entity | STANDARD' with products GANTANOL 500MG and "
                  "GANTANOL-DS 1GM tablets (V21-C09). Sibling suspension NDA013664 verified "
                  "live as '07/01/1965 | ORIG-1 | Approval | Type 5' (V21-C10) - the class/date "
                  "inversion is a genuine FDA-data condition; sulfamethoxazole counts once."),
    "NDA017694": ("Live 2026-09-19: twin application NDA017690 verified as ORIG-1/AP/19761228/"
                  "TYPE 5 with the IDENTICAL product string and the same holder, and FDA's "
                  "2016 approval letter covers both 017690s005 and 017694s052 (V21-C11) - a "
                  "documented duplicate-product condition; loperamide counts once via this "
                  "TYPE 1 row."),
    "NDA017450": ("Same-ingredient TYPE 5 sibling Monistat-Derm cream NDA017494 approved "
                  "1974-01-08, 22 days earlier (payload record; miconazole counts once)."),
}

DECISION_HEADER = ["decision_id", "year", "application_number", "drug_brand", "drug_generic",
                   "company_name", "corporate_lineage_and_ticker", "decision_type", "decision_date",
                   "chemical_type_code", "chemical_type_description", "review_priority", "indication",
                   "regulatory_milestone", "source_url_1", "source_url_2", "verification_status", "notes"]

GAP_HEADER = ["candidate_id", "year", "official_nmes", "enumerated_nme_comparable", "gap_size",
              "candidate_application", "candidate_label", "evidence_mechanism",
              "primary_source_urls", "status", "notes"]


def fail(msg: str) -> None:
    raise SystemExit(f"build_pre1980_decisions_v21: {msg}")


# ---------------------------------------------------------------------------
# verification layers
# ---------------------------------------------------------------------------

def load_payloads() -> tuple[dict[int, list], dict[int, dict]]:
    """Verify SHA-256 of every committed payload and return decisions + requests."""
    decisions: dict[int, list] = {}
    reqs: dict[int, dict] = {}
    for (lo, hi), block in BLOCKS.items():
        d = DATA / "raw" / block
        manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        by_year = {}
        for req in manifest["requests"]:
            if req.get("sha256"):            # skip "skipped-existing" stubs
                by_year[int(req["id"].split("_")[-1])] = req
        for year in range(lo, hi + 1):
            path = d / f"decisions_{year}.json"
            if not path.exists():
                fail(f"missing committed payload: {path}")
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            req = by_year.get(year)
            if req is None or sha != req["sha256"]:
                fail(f"{year}: payload SHA drift vs manifest; refusing to build")
            obj = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(obj.get("decisions"), list) or obj.get("count") != len(obj["decisions"]):
                fail(f"{year}: invalid payload shape")
            if len(obj["decisions"]) != EXPECTED_ORIG_AP[year]:
                fail(f"{year}: payload carries {len(obj['decisions'])} ORIG/AP rows, "
                     f"expected {EXPECTED_ORIG_AP[year]}")
            decisions[year] = obj["decisions"]
            reqs[year] = req
    # dual-run agreement for the 1975-1979 block (run 18 vs run 19)
    run18 = json.loads(RUN18_MANIFEST.read_text(encoding="utf-8"))["manifest"]
    r18 = {int(r["id"].split("_")[-1]): r for r in run18["requests"]}
    for year in V19_YEARS:
        if r18[year]["pages"][0]["raw_sha256"] != reqs[year]["pages"][0]["raw_sha256"]:
            fail(f"{year}: run-18/run-19 raw_sha256 disagree; refusing to build")
        if r18[year]["decisions"] != reqs[year]["decisions"]:
            fail(f"{year}: run-18/run-19 decision counts disagree; refusing to build")
    return decisions, reqs


def load_pre1965() -> dict[int, list]:
    """Verify the 1939-1964 block (fetched this session) for the re-approval screen."""
    d = DATA / "raw" / PRE1965_BLOCK
    manifest_path = d / "manifest.json"
    if not manifest_path.exists():
        fail(f"missing {manifest_path}; the 1939-1964 ORIG/AP block is required for the "
             f"first-appearance screen (fetch_jobs/openfda_orig_decisions_1939_1964.json)")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_year = {int(r["id"].split("_")[-1]): r for r in manifest["requests"] if r.get("sha256")}
    out: dict[int, list] = {}
    failed = []
    for year in range(1939, 1965):
        path = d / f"decisions_{year}.json"
        req = by_year.get(year)
        if req is None or not path.exists():
            failed.append(year)
            continue
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if sha != req["sha256"]:
            fail(f"{year}: pre-1965 payload SHA drift vs manifest")
        obj = json.loads(path.read_text(encoding="utf-8"))
        if obj.get("count") != len(obj.get("decisions") or []):
            fail(f"{year}: invalid pre-1965 payload shape")
        out[year] = obj["decisions"]
    if failed:
        fail(f"pre-1965 payloads missing for {failed}; refusing to build a screen that "
             f"cannot see before 1965")
    return out


def verify_probes(payloads: dict[int, list]) -> dict[str, dict]:
    """One live complete record per new decision row; any disagreement aborts."""
    if not (PROBES_DIR / "manifest.json").exists():
        fail(f"missing {PROBES_DIR}/manifest.json; the live probe layer is required")
    manifest = json.loads((PROBES_DIR / "manifest.json").read_text(encoding="utf-8"))
    entries = {e["id"]: e for e in manifest["requests"] if e.get("sha256")}
    want = []
    for year in NEW_YEARS:
        for d in payloads[year]:
            if (d.get("submission_class_code") or "").upper() in ("TYPE 1", "TYPE 1/4"):
                want.append((year, d))
    want.append((1976, {"application_number": "NDA050495"}))   # explicit gap candidate
    out: dict[str, dict] = {}
    mismatch: list[str] = []
    for year, dec in want:
        appl = dec["application_number"]
        sid = f"probe_{year}_{appl}" if appl != "NDA050495" else "probe_1976gap_NDA050495"
        entry = entries.get(sid)
        if entry is None or entry.get("status") != 200:
            fail(f"{appl}: live probe missing or not HTTP 200 ({sid})")
        path = PROBES_DIR / entry["out"]
        if not path.exists():
            fail(f"{appl}: probe file {entry['out']} missing")
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        if sha != entry["sha256"]:
            fail(f"{appl}: probe SHA drift vs manifest")
        obj = json.loads(path.read_text(encoding="utf-8"))
        results = obj.get("results") or []
        if appl == "NDA050495":
            # gap candidate: record exists but publishes NO submission history
            rec = next((r for r in results if r.get("application_number") == appl), None)
            if rec is None:
                out[appl] = {"status": "ABSENT_LIVE", "sha": sha, "url": entry["url"],
                             "orig_date": "", "class": "", "priority": "", "sponsor": ""}
            elif not rec.get("submissions"):
                out[appl] = {"status": "NO_SUBMISSIONS", "sha": sha, "url": entry["url"],
                             "orig_date": "", "class": "", "priority": "",
                             "sponsor": rec.get("sponsor_name", "")}
            else:
                out[appl] = {"status": "PRESENT_WITH_SUBMISSIONS", "sha": sha, "url": entry["url"],
                             "orig_date": "", "class": "", "priority": "",
                             "sponsor": rec.get("sponsor_name", "")}
            continue
        rec = next((r for r in results if r.get("application_number") == appl), None)
        if rec is None:
            out[appl] = {"status": "ABSENT_LIVE", "sha": sha, "url": entry["url"],
                         "orig_date": "", "class": "", "priority": "", "sponsor": ""}
            mismatch.append(f"{appl}: application ABSENT from live openFDA (payload has it)")
            continue
        orig = [s for s in rec.get("submissions") or []
                if s.get("submission_type") == "ORIG" and s.get("submission_status") == "AP"]
        exp_date = (dec["decision_date"] or "").replace("-", "")
        match = [s for s in orig if s.get("submission_status_date") == exp_date]
        if len(match) != 1:
            out[appl] = {"status": "MISMATCH", "sha": sha, "url": entry["url"],
                         "orig_date": ";".join(s.get("submission_status_date", "") for s in orig),
                         "class": "", "priority": "", "sponsor": rec.get("sponsor_name", "")}
            mismatch.append(f"{appl}: expected exactly 1 live ORIG/AP on {exp_date}, "
                            f"got {len(match)} of {len(orig)}")
            continue
        s = match[0]
        live = {"status": "MATCH", "sha": sha, "url": entry["url"],
                "orig_date": s.get("submission_status_date", ""),
                "class": s.get("submission_class_code", ""),
                "priority": s.get("review_priority", ""),
                "sponsor": rec.get("sponsor_name", "")}
        out[appl] = live
        if (s.get("submission_class_code") or "") != (dec.get("submission_class_code") or ""):
            mismatch.append(f"{appl}: live class {s.get('submission_class_code')!r} != "
                            f"payload {dec.get('submission_class_code')!r}")
        if (s.get("review_priority") or "") != (dec.get("review_priority") or ""):
            mismatch.append(f"{appl}: live priority {s.get('review_priority')!r} != "
                            f"payload {dec.get('review_priority')!r}")
        if (rec.get("sponsor_name") or "") != (dec.get("sponsor_name") or ""):
            mismatch.append(f"{appl}: live holder {rec.get('sponsor_name')!r} != "
                            f"payload {dec.get('sponsor_name')!r}")
    if mismatch:
        fail("live probe disagreement (fail-closed):\n  " + "\n  ".join(mismatch[:25]))
    return out


def verify_populations() -> dict[int, int]:
    """Live ORIG/AP population totals per new year (limit=1 -> meta.results.total)."""
    if not (POPS_DIR / "manifest.json").exists():
        fail(f"missing {POPS_DIR}/manifest.json; the live year-population layer is required")
    manifest = json.loads((POPS_DIR / "manifest.json").read_text(encoding="utf-8"))
    entries = {e["id"]: e for e in manifest["requests"] if e.get("sha256")}
    out: dict[int, int] = {}
    for year in NEW_YEARS:
        entry = entries.get(f"population_{year}")
        if entry is None or entry.get("status") != 200:
            fail(f"{year}: live population capture missing")
        path = POPS_DIR / entry["out"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            fail(f"{year}: population capture SHA drift")
        obj = json.loads(path.read_text(encoding="utf-8"))
        total = ((obj.get("meta") or {}).get("results") or {}).get("total")
        if not isinstance(total, int):
            fail(f"{year}: population capture has no meta.results.total")
        # Years re-queried live in the sandbox this session (V21-C01..C03) are
        # pinned: a capture whose total disagrees is either a stale payload or a
        # drifted query, and the audit text quotes the pinned number verbatim.
        if year in EXPECTED_POPULATION and total != EXPECTED_POPULATION[year]:
            fail(f"{year}: live population capture total {total} != pinned "
                 f"{EXPECTED_POPULATION[year]}; refusing to publish a number the "
                 f"evidence notes do not support")
        out[year] = total
    return out


def load_official() -> dict[str, tuple[str, str]]:
    official: dict[str, tuple[str, str]] = {}
    with (DATA / "fda_official_year_series.csv").open(newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            official[row["year"]] = (row["nmes_approved"], row["ndas_approved"])
    for year in YEARS:
        if official.get(str(year)) != EXPECTED_OFFICIAL[year]:
            fail(f"{year}: official series drift: {official.get(str(year))} != "
                 f"{EXPECTED_OFFICIAL[year]}")
    return official


def ingredients_of(dec: dict) -> set[str]:
    ings = set()
    for x in dec.get("products") or []:
        raw = x.get("active_ingredients")
        if isinstance(raw, list):
            parts = [p.get("name", "") for p in raw]
        else:
            parts = (raw or "").split(";")
        for part in parts:
            part = part.strip().upper()
            m = re.match(r"^([A-Z0-9\-\s/\.\(\),]+?)(?:\s+\d|\s+EQ\s|\s+N/A|\s+\*\*|$)", part)
            name = (m.group(1).strip() if m else part).rstrip(" .")
            if name:
                ings.add(name)
    return ings


def pick_product(dec: dict, appl: str) -> tuple[dict, str, str]:
    """Select the payload product the display names refer to.

    Rule: the product's brand_name equals the mapped brand exactly and its
    active_ingredients contain the mapped ingredient token.  Where that is
    ambiguous (an application publishing both a plain product and combination
    products under one brand) PRODUCT_STARTSWITH pins the exact leading
    ingredient string, so the chosen product is never an accident of ordering.
    """
    _, _, exp_brand, exp_ing = DISPLAY[appl]
    cands = [p for p in dec.get("products") or []
             if (p.get("brand_name") or "") == exp_brand
             and exp_ing in (p.get("active_ingredients") or "").upper()]
    if appl in PRODUCT_STARTSWITH:
        cands = [p for p in cands
                 if (p.get("active_ingredients") or "").upper().startswith(PRODUCT_STARTSWITH[appl])]
    if not cands:
        fail(f"{appl}: no payload product matches brand {exp_brand!r} + ingredient {exp_ing!r}"
             + (f" starting {PRODUCT_STARTSWITH[appl]!r}" if appl in PRODUCT_STARTSWITH else ""))
    return cands[0], exp_brand, exp_ing


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------

def main() -> int:
    payloads, reqs = load_payloads()
    pre1965 = load_pre1965()
    probes = verify_probes(payloads)
    pops = verify_populations()
    official = load_official()

    # first-appearance index over the 1939-1979 payload universe
    universe: dict[int, list] = dict(pre1965)
    universe.update(payloads)
    first: dict[str, tuple] = {}
    for y in sorted(universe):
        for d in sorted(universe[y], key=lambda r: (r["decision_date"], r["application_number"])):
            for ing in ingredients_of(d):
                first.setdefault(ing, (y, d["application_number"], d["decision_date"]))

    evidence_v19 = json.loads(EVIDENCE_V19.read_text(encoding="utf-8"))
    if [c["capture_id"] for c in evidence_v19["captures"]] != [f"V19-C{i:02d}" for i in range(1, 13)]:
        fail("v19 evidence file must carry exactly V19-C01..V19-C12")
    evidence_v21 = json.loads(EVIDENCE_V21.read_text(encoding="utf-8"))
    if [c["capture_id"] for c in evidence_v21["captures"]] != [f"V21-C{i:02d}" for i in range(1, 12)]:
        fail("v21 evidence file must carry exactly V21-C01..V21-C11")

    decision_rows, audit_rows, era_rows = [], [], []
    probe_hits = 0
    for year in YEARS:
        decs = payloads[year]
        t1 = [d for d in decs
              if (d.get("submission_class_code") or "").upper() in ("TYPE 1", "TYPE 1/4")]
        if len(t1) != EXPECTED_T1[year]:
            fail(f"{year}: Type 1/1-4 enumeration is {len(t1)}, expected {EXPECTED_T1[year]}")
        t1.sort(key=lambda d: (d["decision_date"], d["application_number"]))
        blank_unknown = [d for d in decs
                         if (d.get("submission_class_code") or "").upper() in ("", "UNKNOWN")]
        for seq, d in enumerate(t1, 1):
            appl = d["application_number"]
            if appl not in DISPLAY:
                fail(f"{appl}: no explicit display mapping; refusing to guess names")
            brand, generic, _, _ = DISPLAY[appl]
            prod, exp_brand, exp_ing = pick_product(d, appl)
            if not d["decision_date"].startswith(str(year)):
                fail(f"{appl}: decision date outside {year}")
            kind = "NDA" if appl.startswith("NDA") else "BLA"
            num = appl[3:]
            # first-appearance screen (1939-1979) with explicit adjudication
            earlier = []
            for ing in sorted(ingredients_of(d)):
                fy, fapp, fdate = first[ing]
                if not (fy == year and fapp == appl):
                    if (year, appl, ing) not in ALLOWED_EARLIER:
                        fail(f"{appl}: ingredient {ing} first appears {fdate} on {fapp} "
                             f"({fy}); not adjudicated in ALLOWED_EARLIER")
                    earlier.append((ing, fy, fapp, fdate))
            if earlier:
                screen = "; ".join(
                    f"{ing}: first appears {fdate} on {fapp} ({fy}) - "
                    f"{ALLOWED_EARLIER[(year, appl, ing)]}" for ing, fy, fapp, fdate in earlier)
            else:
                screen = ("first appearance within the committed 1939-1979 openFDA payload "
                          "universe (Drugs@FDA coverage before 1965 is incomplete, so this "
                          "is a re-approval screen, not proof of first marketing)")
            prods = "; ".join(
                f"{x.get('brand_name', '')} ({x.get('active_ingredients', '')}; "
                f"{x.get('dosage_form', '')}; {x.get('marketing_status', '')})"
                for x in d.get("products") or [])
            form = (prod.get("dosage_form") or "").lower()
            route = (prod.get("route") or "").lower()
            mkt = (prod.get("marketing_status") or "")
            # Where several payload product records carry the displayed brand, the
            # visible column must not pretend one of them is "the" approved
            # product: it names the multiplicity and lists the verbatim
            # form/route strings instead of silently picking the first.
            same_brand = [x for x in d.get("products") or []
                          if (x.get("brand_name") or "") == exp_brand]
            if len({(x.get("dosage_form", ""), x.get("route", ""),
                     x.get("marketing_status", "")) for x in same_brand}) > 1:
                forms = sorted({f"{x.get('dosage_form', '')}; {x.get('route', '')}"
                                for x in same_brand})
                statuses = sorted({(x.get("marketing_status") or "") for x in same_brand})
                head = (f"{brand} ({generic}) product - {len(same_brand)} payload product "
                        f"records carry this brand and disagree on form/route/marketing "
                        f"status (verbatim form; route: {', '.join(forms)}); published "
                        f"marketing status {' / '.join(statuses)}")
                tail = "."
            else:
                head = f"{brand} ({generic}) {form} ({route}) product"
                tail = f"; current marketing status {mkt}."
            milestone = (f"{head}; ORIG-1 approval "
                         f"{d['decision_date']}; {d['submission_class_code_description']}; "
                         f"{d['review_priority'] or 'unpublished priority'} review{tail}")
            if year in V19_YEARS:
                # reproduce the v19 note wording verbatim
                live = LIVE_V19.get(appl, "No live single-record probe was issued for this row "
                                          "in v19; it rests on the dual-run payload extraction "
                                          "and is re-verifiable at the two source URLs.")
                notes = (f"v19 2026-09-19 added from the committed openFDA Drugs@FDA payloads "
                         f"(dual-run byte-identical raw responses; run-18 vs run-19 raw_sha256 "
                         f"agree; payload SHA verified against the run-19 manifest). Payload: "
                         f"ORIG/AP {d['decision_date']}, {d['submission_class_code']}, "
                         f"{d['review_priority'] or 'priority unpublished'}, holder "
                         f"{d['sponsor_name']}, product {prods}. Ingredient screen: {screen.rstrip('.')} "
                         f"{live} No ticker or indication asserted.")
            else:
                pr = probes.get(appl, {})
                probe_hits += 1 if pr.get("status") == "MATCH" else 0
                if pr.get("status") != "MATCH":
                    fail(f"{appl}: expected a live MATCH probe, got {pr.get('status')!r}")
                notes = (f"v21 2026-09-19 added from the committed openFDA Drugs@FDA payloads "
                         f"(SHA-256 verified against the runner manifest). Payload: ORIG/AP "
                         f"{d['decision_date']}, {d['submission_class_code']}, "
                         f"{d['review_priority'] or 'priority unpublished'}, holder "
                         f"{d['sponsor_name']}, product {prods}. Display product selected from "
                         f"the payload: {prod.get('brand_name', '')} "
                         f"({prod.get('active_ingredients', '')}; {prod.get('dosage_form', '')}; "
                         f"{prod.get('route', '')}; {prod.get('marketing_status', '')}). "
                         f"Ingredient screen: {screen.rstrip('.')} Live per-row probe 2026-09-19 "
                         f"(data/raw/pre1980_row_probes_1965_1976/probe_{appl}.json, SHA-256 "
                         f"{pr['sha'][:16]}...): live ORIG-1/AP/{pr['orig_date']}/"
                         f"{pr['class']}/{pr['priority'] or 'priority unpublished'}, holder "
                         f"{pr['sponsor']} - date, class, priority and holder all equal the "
                         f"payload. Brand and holder are as Drugs@FDA publishes them today, "
                         f"not asserted as approval-era names. No ticker or indication asserted. "
                         f"{LIVE_V21.get(appl, '')}").strip()
            decision_rows.append({
                "decision_id": f"PRE1980-{year}-{seq:02d}", "year": year,
                "application_number": f"{kind} {num}", "drug_brand": brand,
                "drug_generic": generic,
                "company_name": (f"{d['sponsor_name']} (Drugs@FDA holder of record; "
                                 f"approval-era applicant lineage not pinned)"),
                "corporate_lineage_and_ticker": ("No ticker assigned: historical applicant and "
                                                 "period listing require separate primary-source "
                                                 "corporate resolution; no inference made."),
                "decision_type": f"APPROVAL (ORIGINAL {kind})", "decision_date": d["decision_date"],
                "chemical_type_code": d["submission_class_code"],
                "chemical_type_description": d["submission_class_code_description"],
                "review_priority": d.get("review_priority", ""), "indication": "",
                "regulatory_milestone": milestone,
                "source_url_1": DRUGSFDA.format(num=num),
                "source_url_2": OPENFDA_Q.format(appl=appl),
                "verification_status": "Verified", "notes": notes,
            })

        official_nme, official_nda = official[str(year)]
        comparable = len(t1)
        delta = comparable - int(official_nme)
        verdict = ("PROJECT_SHORT_FLAGGED" if delta < 0
                   else ("PROJECT_EXCEEDS_OFFICIAL" if delta > 0 else "MATCH"))
        pop = pops.get(year, EXPECTED_POPULATION.get(year))
        audit_rows.append({
            "year": year, "official_nmes_approved": official_nme,
            "official_ndas_approved": official_nda,
            "payload_orig_ap_total": len(decs),
            "payload_type1_14_rows": len(t1),
            "payload_blank_unknown_rows": len(blank_unknown),
            "verified_decision_rows": len(t1),
            "nme_comparable_rows": comparable,
            "delta_nme_comparable_vs_official": delta,
            "verdict": verdict,
            "live_population_total": pop,
            "live_population_check": (
                f"Live 2026-09-19 ORIG/AP population re-query meta.results.total = {pop} "
                f"(V21 year-population capture)" if year in NEW_YEARS else
                f"Live 2026-09-19 ORIG/AP population re-query meta.results.total = {pop} "
                f"(v19 capture)"),
            "live_captures": AUDIT_CAPTURES.get(year, ""),
            "key_irregularities": AUDIT_IRREGULARITIES[year],
            "evidence_note": AUDIT_NOTES[year],
            "source_urls": ("https://www.fda.gov/about-fda/histories-fda-regulated-products/"
                            "summary-nda-approvals-receipts-1938-present|"
                            f"data/raw/{block_of(year)}/decisions_{year}.json|"
                            "data/raw/pre1980_row_probes_1965_1976/manifest.json|"
                            "data/raw/pre1980_year_populations_1965_1976/manifest.json"),
        })
        pri = sum(1 for r in decision_rows
                  if r["year"] == year and r["review_priority"] == "PRIORITY")
        std = sum(1 for r in decision_rows
                  if r["year"] == year and r["review_priority"] == "STANDARD")
        unk = sum(1 for r in decision_rows
                  if r["year"] == year and r["review_priority"] not in ("PRIORITY", "STANDARD"))
        brands = ", ".join(r["drug_brand"] for r in decision_rows if r["year"] == year)
        era_rows.append({
            "year": year, "total_nmes_approved": len(t1),
            "official_fda_nme_count": official_nme, "nme_comparable_rows": comparable,
            "official_series_delta": delta,
            "verified_decisions_tracked": len(t1), "priority_reviews": pri,
            "standard_reviews": std, "unpublished_priority_reviews": unk,
            "orphan_drug_act_status": ("The Orphan Drug Act had not yet been enacted; no "
                                       "orphan-law framework applied to these approvals."),
            "statutory_framework": ("Pre-Orphan Drug Act federal NDA framework; the 1962 "
                                    "Kefauver-Harris amendments governed efficacy and safety "
                                    "review."),
            "landmark_approvals": brands,
            "historical_significance": ERA_NOTES[year],
            "primary_source_basis": (
                f"openFDA Drugs@FDA ORIG/AP enumeration {year} "
                f"(data/raw/{block_of(year)}/decisions_{year}.json: {reqs[year]['decisions']} "
                f"original approvals; {len(t1)} TYPE 1/1-4 applications; payload SHA-256 "
                f"verified against the runner manifest"
                + ("; run-18/run-19 dual-run raw_sha256 agreement re-checked" if year in V19_YEARS else "")
                + f"). Official counts from data/fda_official_year_series.csv "
                f"({official_nme} NMEs, {official_nda} NDAs approved), re-read live from the FDA "
                f"history page 2026-09-19 (V21-C08). Live probes and population re-queries in "
                f"data/raw/pre1980_row_probes_1965_1976/ and "
                f"data/raw/pre1980_year_populations_1965_1976/."),
        })

    cap_rows = []
    for ev, table in ((evidence_v19, "pre1980_fda_decisions.csv"),
                      (evidence_v21, "pre1980_fda_decisions.csv")):
        for c in ev["captures"]:
            cap_rows.append({
                "capture_id": c["capture_id"], "capture_date": ev["capture_date"],
                "system": c["system"], "subject": c["subject"], "url": c["query_url"],
                "finding_summary": c["finding"], "project_table_affected": table,
                "project_row_ids": c["project_row_ids"], "project_effect": c["project_effect"],
                "verbatim_evidence_ref": (
                    "data/raw/source_captures_2026_09_19/"
                    f"live_primary_captures_{'v19' if c['capture_id'].startswith('V19') else 'v21'}"
                    "_2026_09_19.json"),
            })

    gap_rows = build_gap_rows(payloads, probes, official)

    def write(name: str, header: list[str], rows: list[dict]) -> None:
        with (DATA / name).open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=header)
            w.writeheader()
            w.writerows(rows)

    write("pre1980_fda_decisions.csv", DECISION_HEADER, decision_rows)
    write("pre1980_year_audit.csv", list(audit_rows[0].keys()), audit_rows)
    write("pre1980_era_analysis.csv", list(era_rows[0].keys()), era_rows)
    write("pre1980_primary_captures_index.csv", list(cap_rows[0].keys()), cap_rows)
    write("missing_nme_candidates.csv", GAP_HEADER, gap_rows)
    print(f"v21: {len(decision_rows)} decisions ({probe_hits} live MATCH probes), "
          f"{len(audit_rows)} audit rows, {len(era_rows)} era rows, "
          f"{len(cap_rows)} captures, {len(gap_rows)} gap-candidate rows")
    return 0


def block_of(year: int) -> str:
    for (lo, hi), block in BLOCKS.items():
        if lo <= year <= hi:
            return block
    raise AssertionError(year)


def build_gap_rows(payloads: dict[int, list], probes: dict[str, dict],
                   official: dict[str, tuple[str, str]]) -> list[dict]:
    """One row per year with a sized official-vs-enumeration gap, plus named candidates."""
    named = {
        1976: [("NDA050495", "amikacin (Amikin) injection",
                "MECHANISM_PROVEN_NO_SUBMISSION_HISTORY",
                "openFDA drug/drugsfda record EXISTS for NDA050495 (holder APOTHECON, two "
                "AMIKIN amikacin sulfate injectable products, both Discontinued) but carries NO "
                "submissions array, so no ORIG/AP submission exists for any year query to match; "
                "the Drugs@FDA website page renders the products table with no 'Approval Date(s) "
                "and History' section at all. This is the second distinct invisibility mechanism "
                "(record present, history absent) alongside the Seldane class (record absent "
                "outright).",
                "https://api.fda.gov/drug/drugsfda.json?search=application_number:%22NDA050495%22|"
                "https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process"
                "&varApplNo=050495",
                "NAMED_CANDIDATE_NOT_ADDED",
                "Named from NCATS Inxight Drugs (NIH) 'First approved in 1976' for amikacin, then "
                "probed live on both FDA surfaces (V21-C06/V21-C07): the openFDA record exists "
                "with NO submissions array and the Drugs@FDA page has no approval-history "
                "section, so no ORIG/AP year query can ever return it. NOT added to the decision "
                "table: FDA publishes no approval date, class or priority for it, and the project "
                "never fills those in. The 1976 gap is sized 1 (22 official NMEs vs 21 enumerated), "
                "so amikacin is a candidate for that single slot, not a confirmed identity - "
                "confirming it needs the contemporaneous record.")],
        1979: [("NDA018103", "Selacryn (ticrynafen) tablets",
                "MECHANISM_PROVEN_NAMED_NDA_ABSENT_FROM_ALL_REMAINING_FDA_FILES",
                "Federal Register 61 FR 25228 (1996-05-20, Docket 96N-0151) still cites NDA 18-103 "
                "for Selacryn (ticrynafen) Tablets held by SmithKline Beecham Pharmaceuticals. "
                "Application 018103 is absent from Applications_all_types.txt (29,336 rows), "
                "Applications_appl_window.txt, Submissions_1965_1979.txt, Products_appl_window.txt, "
                "and every 1965-1979 ORIG/AP payload (0 hits). This is the Seldane-class purge "
                "proven by a named NDA: the Federal Register still cites the application, but no "
                "remaining FDA database file carries it. Distinct from amikacin NDA050495, which "
                "still has an openFDA shell with no submissions array.",
                "https://www.govinfo.gov/content/pkg/FR-1996-05-20/html/96-12570.htm|"
                "https://www.accessdata.fda.gov/scripts/cder/daf/index.cfm?event=overview.process"
                "&varApplNo=018103",
                "NAMED_CANDIDATE_NOT_ADDED",
                "Named from Federal Register 61 FR 25228 (1996-05-20, Docket 96N-0151, FR Doc "
                "96-12570): FDA withdrew NDA 18-103 Selacryn (ticrynafen) Tablets at SmithKline "
                "Beecham's request; the company 'discontinued marketing the product in 1980 "
                "because of liver toxicity observed after approval of the NDA.' NCATS Inxight "
                "Drugs cites the Orange Book NME Appendix 1950-1993 as the source for a 1979 "
                "first-approval year. Secondary literature (Pink Sheet/Citeline, ScienceDirect, "
                "Wikipedia) reports FDA approval on 1979-05-02; that calendar date is NOT in "
                "remaining FDA databases and is recorded as literature-reported, not as an "
                "FDA-database date. The 1979 Type 1 list has no May 2 approval (gap Apr 4 Ceclor "
                "NDA050521 -> May 15 Nubain NDA018024). NOT added to the decision table: FDA "
                "publishes no remaining ORIG date, class or priority for 018103, and the project "
                "never fills those in. The 1979 gap is sized 1 (14 official NMEs vs 13 enumerated), "
                "so Selacryn is a candidate for that single slot, not a confirmed identity - "
                "confirming it needs the 1989 CDER statistical typescript.")],
    }
    year_gap_tail = {
        1977: (" v22 (2026-09-20): the 32 KIND_UNRESOLVED ORIG/AP rows for 1977 include 0 "
               "TYPE 1/1-4 (27 unpublished class, 2 TYPE 5, 2 TYPE 3, 1 TYPE 2); public "
               "Drugs@FDA/openFDA/Federal-Register searches this session named no 1977 NME. "
               "The remaining 8 still require the 1989 CDER typescript."),
        1978: (" v22 (2026-09-20): KIND_UNRESOLVED 012043 (1978-10-16, TYPE 1/4 STANDARD) is "
               "inventory, not a gap-filler - 1978 has no official shortfall."),
    }
    rows = []
    for year in YEARS:
        official_nme, _ = official[str(year)]
        t1 = [d for d in payloads[year]
              if (d.get("submission_class_code") or "").upper() in ("TYPE 1", "TYPE 1/4")]
        gap = int(official_nme) - len(t1)
        cands = named.get(year, [])
        if not cands:
            rows.append({
                "candidate_id": f"GAP-{year}-00", "year": year,
                "official_nmes": official_nme, "enumerated_nme_comparable": len(t1),
                "gap_size": gap, "candidate_application": "",
                "candidate_label": "",
                "evidence_mechanism": ("NO_CANDIDATE_NAMEABLE_FROM_PUBLIC_FDA_DATA" if gap > 0
                                       else "NO_GAP"),
                "primary_source_urls": ("https://www.fda.gov/about-fda/histories-fda-regulated-"
                                        "products/summary-nda-approvals-receipts-1938-present"),
                "status": ("UNRESOLVED_NEEDS_1989_CDER_TYPESCRIPT" if gap > 0 else "CLOSED"),
                "notes": ((f"Official {official_nme} NMEs vs {len(t1)} enumerated TYPE 1/1-4 "
                           f"payload rows (delta {gap}). " +
                           ("The v20 full-Drugs@FDA-database cross-check proved 0 payload-invisible "
                            "originals for 1977-1979, so the missing NMEs sit in applications no "
                            "longer present anywhere in modern FDA databases; naming them requires "
                            "the 1989 CDER 'Offices of Drug Evaluation: Statistical Report' "
                            "(FDA History Office Files) or the contemporaneous annual report."
                            if gap > 0 else
                            "No shortfall against the official series for this year.")
                           + year_gap_tail.get(year, ""))
                          if gap != 0 else
                          f"Enumerated rows exceed the official count by {-gap}; see "
                          f"data/pre1980_year_audit.csv for the adjudication."),
            })
            continue
        for i, (appl, label, mech, ev, urls, status, note) in enumerate(cands, 1):
            rows.append({
                "candidate_id": f"GAP-{year}-{i:02d}", "year": year,
                "official_nmes": official_nme, "enumerated_nme_comparable": len(t1),
                "gap_size": gap, "candidate_application": appl, "candidate_label": label,
                "evidence_mechanism": mech, "primary_source_urls": urls, "status": status,
                "notes": note,
            })
    return rows


# ---------------------------------------------------------------------------
# per-year narrative (audit + era).  Facts only; every number is pinned above.
# ---------------------------------------------------------------------------
AUDIT_CAPTURES = {
    1965: "V21-C02", 1970: "V21-C03", 1976: "V21-C01; V21-C06; V21-C07",
    1977: "V19-C01; V19-C04; V19-C06; V19-C10",
    1978: "V19-C02; V19-C05; V19-C07; V19-C12; V22-C03",
    1979: "V19-C03; V19-C08; V19-C09; V19-C11; V22-C01; V22-C02",
}

AUDIT_IRREGULARITIES = {
    1965: ("Sulfamethoxazole class/date inversion: suspension NDA013664 TYPE 5 approved "
           "1965-07-01, 55 days BEFORE the TYPE 1 tablet NDA012715 (1965-08-25), same holder "
           "ROCHE - both verified live on the Drugs@FDA website (V21-C09/V21-C10); counted once "
           "via the TYPE 1 row. Second class/date inversion surfaced by the extended 1939-1979 "
           "screen: Cordran NDA012806 (TYPE 1, 1965-10-18) carries the same brand and ingredient "
           "as Cordran lotion NDA013790 (TYPE 3, 1963-03-19, INA PHARMS) - a supplemental-class "
           "record 27 months BEFORE the TYPE 1 record with no parent application published in "
           "the payloads; flurandrenolide counted once via the TYPE 1 row, flagged not "
           "corrected. 2 blank-class and 5 UNKNOWN-class payload rows (FDA publishes no "
           "submission class); Santyl BLA101995 publishes UNKNOWN priority. THAM NDA013025 is "
           "TYPE 1/4 and is the +1 on the NME-comparable basis."),
    1966: ("Ovulen-21 NDA016029 is TYPE 1/4 (NME + new combination) and is the +1 on the "
           "NME-comparable basis; Type-1-only count is 6. 2 blank-class and 1 UNKNOWN-class "
           "payload rows. Three separate applications share the 1966-07-01 ORIG date (Sulla, "
           "Vercyte, Lasix) - published verbatim, not merged."),
    1967: ("No first-appearance flags in the Type-1 set. 1 blank-class and 2 UNKNOWN-class "
           "payload rows. Hydroxyurea NDA016295 carries both DROXIA and HYDREA products under "
           "one application; the display brand is the payload's first product (DROXIA) and no "
           "approval-era trade name is asserted."),
    1968: ("Smallest pre-1980 enumeration (4 rows) against 14 official NMEs: the largest relative "
           "shortfall in the block (-10). Ovral NDA016672 is TYPE 1/4. 3 blank-class payload "
           "rows. The official NDA-approvals count (59) is also ~2.7x the payload ORIG/AP "
           "population (22), i.e. the shortfall is not specific to NMEs."),
    1969: ("PROJECT_EXCEEDS_OFFICIAL: 8 enumerated vs 5 official (+3). Every one of the 8 was "
           "checked individually (Quide, Teslac, Travase, Cytarabine, Matulane, Sinequan, "
           "Bilopaque, HMS) and each is a payload TYPE 1 original with a live MATCH probe; the "
           "divergence is between FDA's contemporaneous NME statistic and its modern "
           "application-level classification, and is published as measured, not smoothed. "
           "Travase NDA012828 and QUIDE NDA013615 carry 1950s-series application numbers with "
           "1969 ORIG dates - flagged as numbering/date pairings, dates confirmed live."),
    1970: ("Cuprimine NDA019853 (penicillamine, ORIG-1 1970-12-04, TYPE 1, STANDARD) carries an "
           "application number out of sequence for 1970; the date is confirmed on both openFDA "
           "and the Drugs@FDA website (V21-C04/V21-C05), so the row is published as FDA carries "
           "it and the numbering anomaly is flagged for review (same class as the open "
           "NDA022046 artifact). 5 blank-class and 3 UNKNOWN-class payload rows."),
    1971: ("Only 7 TYPE 1 rows among 48 ORIG/AP approvals - 31 TYPE 5 (new formulation/manufacturer) "
           "and 8 UNKNOWN-class rows; the year's low NME-comparable count is an FDA "
           "classification property of the payload, verified row by row. No first-appearance "
           "flags in the Type-1 set."),
    1972: ("Marcaine NDA016964 publishes 10 products across four brand strings; the display "
           "product is the plain MARCAINE HYDROCHLORIDE (bupivacaine hydrochloride) product and "
           "all 10 are listed verbatim in the row notes. Epinephrine bitartrate appears as a "
           "combination component (adjudicated). 1 blank-class and 6 UNKNOWN-class rows."),
    1973: ("Septra NDA017376 is TYPE 1/4 (sulfamethoxazole appears earlier on Gantanol). "
           "Blenoxane NDA050443 publishes UNKNOWN priority. Catapres tablets NDA017407 "
           "(TYPE 3, PRIORITY, BOEHRINGER INGELHEIM) publish clonidine with the same top-level "
           "payload date (1974-09-03) as Combipres NDA017503 (TYPE 1/4, 1974-09-03) - the "
           "committed payloads support no earlier date, so the pairing is published as "
           "same-day and clonidine is adjudicated a combination component. 1 UNKNOWN-class "
           "payload row."),
    1974: ("Largest pre-1980 enumeration (16 rows). Miconazole sibling inversion: Monistat-Derm "
           "cream NDA017494 TYPE 5 approved 1974-01-08, 22 days before the TYPE 1 Monistat 7 "
           "(1974-01-30) - counted once. Combipres NDA017503 is TYPE 1/4. Pre-Pen BLA050114 is a "
           "biologics-licence-numbered application carrying a TYPE 1 class. 57 TYPE 5 rows and "
           "no blank/UNKNOWN rows in the year."),
    1975: ("Sinemet NDA017555 is TYPE 1/4 (levodopa appears earlier on Larodopa). Loxitane "
           "NDA017525 publishes a Federal Register 'discontinued or withdrawn' note on one "
           "product - reproduced verbatim. 29 TYPE 5 rows; 1 blank-class row."),
    1976: ("Gap candidate NAMED: amikacin (Amikin) NDA050495 - openFDA record present with NO "
           "submissions array and a Drugs@FDA page with no approval-history section "
           "(V21-C06/V21-C07), so it can never appear in an ORIG/AP year query. Imodium "
           "duplicate-product condition: NDA017690 carries the identical product with a TYPE 5 "
           "ORIG on the same day (V21-C11). Duranest publishes both etidocaine and "
           "etidocaine/epinephrine products. 1 blank-class and 1 UNKNOWN-class row."),
    1977: ("none in the Type-1 set: all 17 ingredients first-in-payloads; no blank/UNKNOWN-class "
           "payload rows in 1977"),
    1978: ("MOTOFEN NDA017744 is TYPE 1/4 (NME + new combination; verified live V19-C07) and is "
           "the +1 on the NME-comparable basis used for every crosswalk year; Type-1-only count "
           "is 17 = official. Its atropine sulfate component first appears in the payloads on "
           "Lomotil NDA012462 (TYPE 4, 1960-09-15, PFIZER) - adjudicated combination component "
           "of the Motofen pairing, not a second NME (the extended 1939-1979 screen made the "
           "1960 first appearance visible). KINLYTIC BLA021846 (urokinase, first-in-payloads) "
           "publishes UNKNOWN class/priority (verified live V19-C12) and is NOT counted pending "
           "an application-level NME source. PREMARIN NDA020216 UNKNOWN is conjugated estrogens "
           "(legacy, not an NME). Five blank-class rows are IV electrolytes/dextrose (B Braun) "
           "and bupivacaine - marketed ingredients."),
    1979: ("Cyclapen inversion: tablet NDA050509 TYPE 3 approved 1979-09-13, one day BEFORE "
           "suspension NDA050508 TYPE 1 approved 1979-09-14 (same ingredient, same sponsor "
           "WYETH AYERST); verified live in both directions (V19-C08/V19-C11) so the inversion "
           "is a genuine FDA-data condition; counted once via the Type-1 row. Five blank-class "
           "rows: furosemide (molecule first approved 1966-07-01 per the payloads), IV "
           "electrolytes/dextrose, and potassium iodide (Thyro-Block, historically marketed) - "
           "none an NME. v22 NAMED candidate (not added): Selacryn (ticrynafen) NDA 18-103 / "
           "NDA018103, Federal Register 61 FR 25228 (1996-05-20); application 018103 is absent "
           "from every remaining FDA database file (Applications_all_types, Submissions, "
           "Products, payloads) - Seldane-class purge proven by a named NDA."),
}

AUDIT_NOTES = {
    1965: ("Official 18 NMEs vs 11 NME-comparable payload rows (10 TYPE 1 + 1 TYPE 1/4): "
           "shortfall of 7. Live population re-query 2026-09-19 total=52 equals the manifest "
           "n_raw_records (52) for the year. Every one of the 11 rows carries a live per-row "
           "MATCH probe. The v20 full-database cross-check proved 0 payload-invisible originals "
           "for 1977-1979; the same conclusion cannot be transferred to 1965 without repeating "
           "that cross-check for the year."),
    1966: ("Official 10 NMEs vs 7 NME-comparable payload rows (6 TYPE 1 + 1 TYPE 1/4): shortfall "
           "of 3. Official NDA approvals 40 vs 22 payload ORIG/AP applications - the official "
           "contemporaneous counts include applications no longer present in the modern "
           "database."),
    1967: ("Official 16 NMEs vs 13 NME-comparable payload rows: shortfall of 3. The official "
           "NDA-approvals figure for 1967 (189) is 5.9x the payload ORIG/AP application "
           "population (32) - the single largest official-vs-database divergence in the block, "
           "published verbatim from both sources."),
    1968: ("Official 14 NMEs vs 4 NME-comparable payload rows (3 TYPE 1 + 1 TYPE 1/4): shortfall "
           "of 10, the largest pre-1980 shortfall after 1975. Naming these 10 requires the 1989 "
           "CDER statistical typescript; no candidate is asserted."),
    1969: ("Official 5 NMEs vs 8 NME-comparable payload rows: the project EXCEEDS the official "
           "count by 3. Each row was probed live and matched field-by-field, so the divergence "
           "is between FDA's 1969 NME statistic and its current application-level TYPE 1 "
           "classification. Both numbers are published side by side; neither is adjusted."),
    1970: ("Official 15 NMEs vs 11 NME-comparable payload rows: shortfall of 4. Live population "
           "re-query 2026-09-19 total=74 equals the manifest n_raw_records (74)."),
    1971: ("Official 12 NMEs vs 7 NME-comparable payload rows: shortfall of 5. 48 ORIG/AP "
           "approvals in the year, of which 31 are TYPE 5 (new formulation or new manufacturer) "
           "and 8 publish no class at all - the enumeration is complete but FDA's TYPE 1 "
           "classification is sparse for this year."),
    1972: ("Official 10 NMEs vs 7 NME-comparable payload rows: shortfall of 3."),
    1973: ("Official 14 NMEs vs 11 NME-comparable payload rows (10 TYPE 1 + 1 TYPE 1/4): "
           "shortfall of 3."),
    1974: ("Official 21 NMEs vs 16 NME-comparable payload rows (15 TYPE 1 + 1 TYPE 1/4): "
           "shortfall of 5."),
    1975: ("Official 20 NMEs vs 9 NME-comparable payload rows (8 TYPE 1 + 1 TYPE 1/4): shortfall "
           "of 11, the largest absolute pre-1980 shortfall."),
    1976: ("Official 22 NMEs vs 21 NME-comparable payload rows: shortfall of 1, and that single "
           "slot now has a NAMED candidate with a proven invisibility mechanism - amikacin "
           "(Amikin) NDA050495, present in openFDA with no submissions array and no approval "
           "history on the Drugs@FDA page (V21-C06/V21-C07). Live population re-query 2026-09-19 "
           "total=619 equals the manifest n_raw_records (619). The candidate is recorded in "
           "data/missing_nme_candidates.csv and is NOT added to the decision table (FDA "
           "publishes no approval date/class/priority for it)."),
    1977: ("Official 25 NMEs vs 17 Type-1 payload rows: shortfall of 8 sits in applications "
           "absent from the Drugs@FDA ORIG/AP payload altogether (the gap class proven for 1985: "
           "Seldane/Protropin/Suprol/Femstat). Naming the 8 requires the 1989 CDER statistical "
           "typescript (pp. 152-199) or the contemporaneous FDA annual report. v20 full-DB "
           "cross-check (2026-09-19): the complete Drugs@FDA database files (fda.gov media 89850 "
           "zip, SHA-manifested) enumerate exactly 42 ORIG/AP approvals for 1977 - identical to "
           "the payload, 0 payload-invisible - so the 8 sit in applications no longer present "
           "anywhere in modern FDA databases, the Seldane purge class. v22 (2026-09-20): the 32 "
           "KIND_UNRESOLVED ORIG/AP rows for 1977 include 0 TYPE 1/1-4, so they cannot name the "
           "8; public Federal Register / Drugs@FDA / openFDA searches this session named no 1977 "
           "NME. The 8 remain unnamed."),
    1978: ("Official 17 NMEs vs 18 NME-comparable payload rows: the project exceeds the official "
           "count by 1 because the NME-comparable basis counts the Type 1/4 Motofen row, "
           "consistent with 1981/1984. No shortfall; the uncounted Kinlytic UNKNOWN-candidate is "
           "flagged, not guessed. v22 (2026-09-20): KIND_UNRESOLVED 012043 (1978-10-16 TYPE 1/4 "
           "STANDARD) is inventory, not a gap-filler."),
    1979: ("Official 14 NMEs vs 13 Type-1 payload rows: shortfall of 1 sits in an application "
           "absent from the ORIG/AP payload (1985-proven gap class). v22 (2026-09-20): that "
           "single slot now has a NAMED candidate - Selacryn (ticrynafen) NDA 18-103 / NDA018103, "
           "named by Federal Register 61 FR 25228 (1996-05-20, Docket 96N-0151). Application "
           "018103 is absent from Applications_all_types.txt, Submissions_1965_1979.txt, "
           "Products_appl_window.txt and every 1965-1979 payload (0 hits). Recorded in "
           "data/missing_nme_candidates.csv as NAMED_CANDIDATE_NOT_ADDED; not added to the "
           "decision table (FDA publishes no remaining ORIG date/class/priority). Confirming "
           "the identity still needs the 1989 CDER statistical typescript."),
}

ERA_NOTES = {
    1965: ("The committed Drugs@FDA extract enumerates 10 TYPE 1 plus 1 TYPE 1/4 original "
           "approvals among 32 ORIG/AP applications. Application-level enumeration, not a "
           "reconstructed contemporaneous statistic. Official series: 18 NMEs (53 NDAs "
           "approved). Live 2026-09-19: population re-query 52 (V21-C02); Gantanol-DS/Gantanol "
           "sulfamethoxazole class inversion verified on the Drugs@FDA website (V21-C09/C10)."),
    1966: ("6 TYPE 1 plus 1 TYPE 1/4 originals among 16 ORIG/AP applications. Official series: "
           "10 NMEs (40 NDAs approved). Three ORIG approvals share 1966-07-01 (Sulla, Vercyte, "
           "Lasix). Every row carries a live per-row MATCH probe."),
    1967: ("13 TYPE 1 originals among 32 ORIG/AP applications - the largest 1960s enumeration. "
           "Official series: 16 NMEs but 189 NDAs approved, i.e. FDA's contemporaneous approval "
           "count is ~6x the applications still present in the modern database."),
    1968: ("3 TYPE 1 plus 1 TYPE 1/4 originals among 22 ORIG/AP applications - the sparsest "
           "pre-1980 year. Official series: 14 NMEs (59 NDAs approved), so 10 official NMEs have "
           "no counterpart in the modern application database. Not guessed, sized and flagged."),
    1969: ("8 TYPE 1 originals among 25 ORIG/AP applications - the project's enumeration EXCEEDS "
           "FDA's official 5 NMEs by 3. All 8 probed live and matched field-by-field; the two "
           "counts measure different things (contemporaneous NME statistic vs current "
           "application-level TYPE 1 classification) and are published side by side."),
    1970: ("11 TYPE 1 originals among 38 ORIG/AP applications. Official series: 15 NMEs (51 NDAs "
           "approved). Carries the Cuprimine NDA019853 numbering anomaly (date confirmed live on "
           "two FDA surfaces) and the landmark levodopa (Larodopa) approval. Live population "
           "re-query 74 (V21-C03)."),
    1971: ("7 TYPE 1 originals among 48 ORIG/AP applications - 31 of the 48 are TYPE 5 new "
           "formulation/new manufacturer records. Official series: 12 NMEs (26 NDAs approved)."),
    1972: ("7 TYPE 1 originals among 29 ORIG/AP applications. Official series: 10 NMEs (57 NDAs "
           "approved). Marcaine NDA016964 alone publishes 10 products under four brand strings."),
    1973: ("10 TYPE 1 plus 1 TYPE 1/4 originals among 43 ORIG/AP applications. Official series: "
           "14 NMEs (50 NDAs approved). Carries the Septra combination row; the same-day "
           "Catapres (TYPE 3, NDA017407) / Combipres (TYPE 1/4, NDA017503) pairing of "
           "1974-09-03 is adjudicated in the 1974 rows."),
    1974: ("15 TYPE 1 plus 1 TYPE 1/4 originals among 73 ORIG/AP applications - the largest "
           "pre-1980 enumeration. Official series: 21 NMEs (85 NDAs approved). Includes amoxicillin "
           "(Amoxil), doxorubicin, ibuprofen (Motrin) and the Pre-Pen biologics-licence-numbered "
           "TYPE 1 application."),
    1975: ("8 TYPE 1 plus 1 TYPE 1/4 originals among 39 ORIG/AP applications. Official series: "
           "20 NMEs (71 NDAs approved) - the largest absolute pre-1980 shortfall (11), sized and "
           "flagged rather than filled in."),
    1976: ("21 TYPE 1 originals among 80 ORIG/AP applications. Official series: 22 NMEs (72 NDAs "
           "approved): shortfall of exactly 1, for which a candidate is now NAMED with a proven "
           "mechanism - amikacin (Amikin) NDA050495 exists in openFDA with no submissions array "
           "and no approval history on its Drugs@FDA page, so no ORIG/AP query can ever return "
           "it (V21-C06/V21-C07). Recorded in data/missing_nme_candidates.csv, not added to the "
           "decision table. Live population re-query 619 (V21-C01)."),
    1977: ("The committed Drugs@FDA extract enumerates 17 TYPE-1 original approvals, all "
           "first-in-payloads ingredients with no blank-class rows. This is an application-level "
           "enumeration, not a reconstructed contemporaneous annual NME statistic. Official "
           "series: 25 NMEs (63 NDAs approved). The official count exceeds the enumeration by 8 "
           "- the largest sized pre-1980 shortfall, in applications absent from the ORIG/AP "
           "payload (1985-proven gap class). Live 2026-09-19: year population 662 re-queried "
           "(V19-C01); Tagamet coexistence + Drugs@FDA ORIG-1 row (V19-C04/V19-C10); Nolvadex "
           "coexistence (V19-C06). Naming the 8 requires the 1989 CDER statistical typescript."),
    1978: ("The committed Drugs@FDA extract enumerates 17 TYPE-1 plus 1 TYPE-1/4 (Motofen) "
           "original approvals. Application-level enumeration, not a reconstructed "
           "contemporaneous statistic. Official series: 17 NMEs (86 NDAs approved). On the "
           "NME-comparable basis used for every crosswalk year the project carries 18 rows (+1, "
           "the Type 1/4 Motofen row verified live V19-C07); Type-1-only count is 17 = official. "
           "One priority value is published UNKNOWN (Elspar BLA101063, verified live V19-C05). "
           "The Kinlytic UNKNOWN-candidate (V19-C12) is flagged, not counted. Live 2026-09-19: "
           "year population 756 re-queried (V19-C02)."),
    1979: ("The committed Drugs@FDA extract enumerates 13 TYPE-1 original approvals. "
           "Application-level enumeration, not a reconstructed contemporaneous statistic. "
           "Official series: 14 NMEs (94 NDAs approved) - shortfall of 1 in a payload-invisible "
           "application. The Cyclapen tablet/suspension class/date inversion (NDA050509 Type 3 "
           "one day before NDA050508 Type 1) is verified live in both directions "
           "(V19-C08/V19-C11) and counted once. Live 2026-09-19: year population 746 re-queried "
           "(V19-C03); Forane verbatim ORIG block (V19-C09)."),
}


if __name__ == "__main__":
    raise SystemExit(main())
