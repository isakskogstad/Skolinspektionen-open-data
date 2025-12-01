"""Data models for Skolinspektionen data."""

from datetime import date
from typing import Optional
from pydantic import BaseModel, Field


class Attachment(BaseModel):
    """A downloadable file attachment."""

    name: str
    url: str
    file_type: Optional[str] = None  # pdf, xlsx, etc.


class Publication(BaseModel):
    """A publication from Skolinspektionen (report, review, etc.)."""

    title: str
    url: str
    slug: str = ""
    published: Optional[date] = None
    updated: Optional[date] = None
    diarienummer: Optional[str] = None
    type: str  # kvalitetsgranskning, regeringsrapporter, etc.
    summary: Optional[str] = None
    themes: list[str] = Field(default_factory=list)
    subjects: list[str] = Field(default_factory=list)  # School subjects (ämnen)
    skolformer: list[str] = Field(default_factory=list)  # School forms
    attachments: list[Attachment] = Field(default_factory=list)

    def model_post_init(self, __context) -> None:
        """Extract slug from URL if not provided."""
        if not self.slug and self.url:
            # /beslut-rapporter/publikationer/kvalitetsgranskning/2025/name/ -> name
            self.slug = self.url.rstrip("/").split("/")[-1]


class PressRelease(BaseModel):
    """A press release from Skolinspektionen."""

    title: str
    url: str
    slug: str = ""
    published: Optional[date] = None

    def model_post_init(self, __context) -> None:
        if not self.slug and self.url:
            self.slug = self.url.rstrip("/").split("/")[-1]


class Decision(BaseModel):
    """A decision/inspection result for a specific school."""

    school_name: str
    school_id: Optional[str] = None  # Skolenhets-ID from Skolverket
    kommun: Optional[str] = None
    region: Optional[str] = None
    huvudman: Optional[str] = None  # School operator
    skolform: Optional[str] = None  # grundskola, gymnasium, etc.
    decision_type: str  # tillsyn, kvalitetsgranskning, etc.
    decision_date: Optional[date] = None
    url: Optional[str] = None
    has_deficiencies: Optional[bool] = None
    summary: Optional[str] = None


class StatisticsFile(BaseModel):
    """A downloadable statistics file (Excel, PDF)."""

    name: str
    url: str
    file_type: str  # xlsx, pdf
    category: str  # tillstand, tillsyn, kvalitetsgranskning
    year: Optional[int] = None
    description: Optional[str] = None


class SearchResult(BaseModel):
    """A search result with relevance score."""

    item: Publication | PressRelease | Decision
    score: float = 1.0
    match_type: str = "exact"  # exact, fuzzy, partial


class Index(BaseModel):
    """The complete index of all scraped data."""

    publications: list[Publication] = Field(default_factory=list)
    press_releases: list[PressRelease] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)
    statistics_files: list[StatisticsFile] = Field(default_factory=list)
    last_updated: Optional[str] = None

    @property
    def total_items(self) -> int:
        return (
            len(self.publications)
            + len(self.press_releases)
            + len(self.decisions)
            + len(self.statistics_files)
        )


# =============================================================================
# TAXONOMIES - Complete filter options from skolinspektionen.se
# =============================================================================

# School forms (Skolformer) - 15 types per Swedish Education Act (Skollag 2010:800)
SKOLFORMER = {
    "forskola": "Förskola",
    "forskoleklass": "Förskoleklass",
    "grundskola": "Grundskola",
    "anpassad-grundskola": "Anpassad grundskola",  # Formerly grundsärskola
    "grundsarskola": "Grundsärskola",  # Legacy name
    "specialskola": "Specialskola",
    "sameskola": "Sameskola",
    "gymnasieskola": "Gymnasieskola",
    "anpassad-gymnasieskola": "Anpassad gymnasieskola",  # Formerly gymnasiesärskola
    "gymnasiesarskola": "Gymnasiesärskola",  # Legacy name
    "komvux": "Kommunal vuxenutbildning (Komvux)",
    "komvux-grundlaggande": "Komvux på grundläggande nivå",
    "komvux-gymnasial": "Komvux på gymnasial nivå",
    "sarvux": "Särskild utbildning för vuxna",  # Now part of Komvux
    "sfi": "Svenska för invandrare (SFI)",
    "fritidshem": "Fritidshem",
    "pedagogisk-omsorg": "Pedagogisk omsorg",
    "oppen-fritidsverksamhet": "Öppen fritidsverksamhet",
}

# Publication types - comprehensive from both skolinspektionen.se and skolverket.se
PUBLICATION_TYPES = {
    # Kvalitetsgranskning types
    "kvalitetsgranskning": "Kvalitetsgranskning",
    "tematisk-kvalitetsgranskning": "Tematisk kvalitetsgranskning",
    "regelbunden-kvalitetsgranskning": "Regelbunden kvalitetsgranskning",
    "planerad-kvalitetsgranskning": "Planerad kvalitetsgranskning",
    # Tillsyn types
    "tillsynsbeslut": "Tillsynsbeslut",
    "regelbunden-tillsyn": "Regelbunden tillsyn",
    "planerad-tillsyn": "Planerad tillsyn",
    "riktad-tillsyn": "Riktad tillsyn",
    "tematisk-tillsyn": "Tematisk tillsyn",
    "oanmald-granskning": "Oanmäld granskning",
    # Enkäter (surveys)
    "skolenkaten": "Skolenkäten",
    "forskoleenkaten": "Förskoleenkäten",
    "foraldraelev-brev": "FöräldraElevbrev",
    # Ombedömning (reassessments)
    "ombedomning-nationella-prov": "Ombedömning nationella prov",
    # Reports
    "regeringsrapporter": "Rapport till regeringen",
    "statistikrapporter": "Statistikrapport",
    "arsrapporter": "Årsrapport",
    "arsredovisning": "Årsredovisning",
    "granskningsrapporter": "Granskningsrapport",
    # Other
    "remissvar": "Remissvar",
    "vagledningar": "Vägledning",
    "nyhetsbrev": "Nyhetsbrev",
    "ovriga-publikationer": "Övriga publikationer",
}

# Inspection themes (Teman) - from Skolinspektionen's inspection focus areas
THEMES = {
    "bedomning-och-betygssattning": "Bedömning och betygssättning",
    "elevers-halsa": "Elevers hälsa",
    "elevhalsa": "Elevhälsa",
    "forskolan": "Förskolan",
    "huvudmannens-styrning": "Huvudmannens styrning",
    "jamstalldhet": "Jämställdhet",
    "kallkritik": "Källkritik",
    "normer-och-varden": "Normer och värden",
    "nyanlanda-och-asylsokande-elever": "Nyanlända och asylsökande elever",
    "stodinsatser": "Stödinsatser",
    "sarskilt-stod": "Särskilt stöd",
    "trygghet-och-studiero": "Trygghet och studiero",
    "vuxenutbildning": "Vuxenutbildning",
    "distansundervisning": "Distansundervisning",
    "digitalisering": "Digitalisering",
    "sprakutveckling": "Språkutveckling",
    "lasning": "Läsning",
    "skrivande": "Skrivande",
    "systematiskt-kvalitetsarbete": "Systematiskt kvalitetsarbete",
    "rektors-ledarskap": "Rektors ledarskap",
    "undervisningens-kvalitet": "Undervisningens kvalitet",
}

# School subjects (Ämnen) - 40+ subjects from Swedish curriculum
SUBJECTS = {
    # Core subjects
    "matematik": "Matematik",
    "svenska": "Svenska",
    "svenska-som-andrasprak": "Svenska som andraspråk",
    "engelska": "Engelska",
    # Natural sciences (NO)
    "biologi": "Biologi",
    "fysik": "Fysik",
    "kemi": "Kemi",
    "naturkunskap": "Naturkunskap",
    # Social sciences (SO)
    "historia": "Historia",
    "geografi": "Geografi",
    "samhallskunskap": "Samhällskunskap",
    "religion": "Religion",
    # Modern languages
    "moderna-sprak": "Moderna språk",
    "franska": "Franska",
    "spanska": "Spanska",
    "tyska": "Tyska",
    # Practical/aesthetic subjects
    "idrott-och-halsa": "Idrott och hälsa",
    "musik": "Musik",
    "bild": "Bild",
    "slojd": "Slöjd",
    "hem-och-konsumentkunskap": "Hem- och konsumentkunskap",
    "teknik": "Teknik",
    # Preschool/Fritids
    "lek-och-larande": "Lek och lärande",
    "omsorg": "Omsorg",
    # Vocational (gymnasiet)
    "yrkesutbildning": "Yrkesutbildning",
    "praktik": "Praktik/APL",
    # Other
    "specialpedagogik": "Specialpedagogik",
    "studie-och-yrkesvagledning": "Studie- och yrkesvägledning",
    "modersmal": "Modersmål",
    "samiska": "Samiska",
}

# Decision/inspection types - comprehensive from both sources
DECISION_TYPES = {
    # Tillsyn (Supervision)
    "etableringskontroll": "Etableringskontroll",
    "forsta-arets-tillsyn": "Första årets tillsyn",
    "planerad-tillsyn": "Planerad tillsyn",
    "regelbunden-tillsyn": "Regelbunden tillsyn",
    "riktad-tillsyn": "Riktad tillsyn",
    "tematisk-tillsyn": "Tematisk tillsyn",
    "oanmald-granskning": "Oanmäld granskning",
    # Kvalitetsgranskning (Quality review)
    "planerad-kvalitetsgranskning": "Planerad kvalitetsgranskning",
    "regelbunden-kvalitetsgranskning": "Regelbunden kvalitetsgranskning",
    "tematisk-kvalitetsgranskning": "Tematisk kvalitetsgranskning",
    # Enkäter (Surveys)
    "skolenkaten": "Skolenkäten",
    "forskoleenkaten": "Förskoleenkäten",
    # Nationella prov (National tests)
    "ombedomning-nationella-prov": "Ombedömning nationella prov",
    # Other
    "anmalan": "Anmälningsärende",
    "uppfoljning": "Uppföljning",
    "foraldraelev-brev": "FöräldraElevbrev",
}

# Swedish regions (for filtering decisions)
REGIONS = {
    "stockholm": "Stockholm",
    "goteborg": "Göteborg",
    "malmo": "Malmö",
    "norr": "Norr",
    "mitt": "Mitt",
    "syd": "Syd",
    "vast": "Väst",
    "ost": "Öst",
    "utlandsskola": "Utlandsskola",
}

# Terms/semesters (for Skolenkäten)
TERMINER = {
    "vt": "Vårtermin",
    "ht": "Hösttermin",
}

# Year range for publications (2009-2025)
YEAR_RANGE = range(2009, 2026)


# =============================================================================
# SKOLENKÄTEN DATA MODELS
# =============================================================================


class SkolenkatResult(BaseModel):
    """Survey result for a single school from Skolenkäten."""

    # School identification
    org_nummer: Optional[str] = None  # Organization number
    huvudman: str  # Principal/operator
    kommun: Optional[str] = None  # Municipality
    skolenhetskod: str  # School unit code
    skolenhet: str  # School name

    # Response metadata
    antal_i_gruppen: Optional[int] = None  # Number in group
    antal_svar: Optional[int] = None  # Number of responses
    svarsfrekvens: Optional[float] = None  # Response rate (0-1)

    # Survey metadata
    year: int  # Survey year
    term: Optional[str] = None  # vt (spring) or ht (fall)
    respondent_type: str  # elever-ak-5, elever-ak-8, larare, vardnadshavare, etc.
    skolform: Optional[str] = None  # grundskola, gymnasieskola, etc.

    # Index scores (1-10 scale)
    index_information: Optional[float] = None  # Information om utbildningen
    index_stimulans: Optional[float] = None  # Stimulans
    index_stod: Optional[float] = None  # Stöd
    index_kritiskt_tankande: Optional[float] = None  # Kritiskt tänkande
    index_bemotande_larare: Optional[float] = None  # Bemötande - lärare
    index_bemotande_elever: Optional[float] = None  # Bemötande - elever
    index_inflytande: Optional[float] = None  # Inflytande
    index_studiero: Optional[float] = None  # Studiero
    index_trygghet: Optional[float] = None  # Trygghet
    index_forhindra_krankningar: Optional[float] = None  # Förhindra kränkningar
    index_elevhalsa: Optional[float] = None  # Elevhälsa
    index_nojdhet: Optional[float] = None  # Övergripande nöjdhet


class SkolenkatSummary(BaseModel):
    """Summary statistics from Skolenkäten data."""

    year: int
    term: Optional[str] = None
    respondent_type: str
    total_schools: int = 0
    total_responses: int = 0
    average_response_rate: Optional[float] = None

    # National average index scores
    national_index_information: Optional[float] = None
    national_index_stimulans: Optional[float] = None
    national_index_stod: Optional[float] = None
    national_index_kritiskt_tankande: Optional[float] = None
    national_index_bemotande_larare: Optional[float] = None
    national_index_bemotande_elever: Optional[float] = None
    national_index_inflytande: Optional[float] = None
    national_index_studiero: Optional[float] = None
    national_index_trygghet: Optional[float] = None
    national_index_forhindra_krankningar: Optional[float] = None
    national_index_elevhalsa: Optional[float] = None
    national_index_nojdhet: Optional[float] = None


class TillstandBeslut(BaseModel):
    """A permit decision for starting or expanding an independent school."""

    # Metadata
    year: int  # Decision year (from filename/path)
    skolstart_lasar: str  # School year when starting (e.g., "2024-25")

    # Basic information
    arendenummer: str  # Case number (e.g., "SI 2023:1204")
    kommun: str  # Municipality
    skola: str  # School name
    sokande: str  # Applicant/operator
    skolform: str  # School form (Grundskola, Gymnasieskola, etc.)
    ansokningstyp: str  # Application type (Nyetablering, Utökning)
    beslutstyp: str  # Overall decision type (Godkännande, Avslag, Avskrivning)

    # Grade-level decisions for grundskola (None = not applicable)
    beslut_ak1: Optional[str] = None
    beslut_ak2: Optional[str] = None
    beslut_ak3: Optional[str] = None
    beslut_ak4: Optional[str] = None
    beslut_ak5: Optional[str] = None
    beslut_ak6: Optional[str] = None
    beslut_ak7: Optional[str] = None
    beslut_ak8: Optional[str] = None
    beslut_ak9: Optional[str] = None

    # Other school forms
    beslut_forskoleklass: Optional[str] = None
    beslut_fritidshem: Optional[str] = None

    # Gymnasieskola programs (None = not applicable)
    gymnasie_programs: Optional[dict[str, str]] = None  # program name -> decision


class IndividArendeStat(BaseModel):
    """Statistics for individual case handling (anmälningsärenden/BEO)."""

    year: int
    kategori: str  # Type of case
    inkomna: int = 0  # Cases received
    beslutade: int = 0  # Cases decided
    brister_konstaterade: int = 0  # Cases with deficiencies found
    andel_med_brister: Optional[float] = None


# Skolenkäten respondent types
SKOLENKATEN_RESPONDENT_TYPES = {
    "elever-grundskola-ak-5": "Elever grundskola åk 5",
    "elever-grundskola-ak-8": "Elever grundskola åk 8",
    "elever-gymnasieskola-ar-2": "Elever gymnasieskola år 2",
    "larare-grundskola": "Lärare grundskola åk 1-9",
    "larare-gymnasieskola": "Lärare gymnasieskola",
    "vardnadshavare-forskoleklass": "Vårdnadshavare förskoleklass",
    "vardnadshavare-grundskola": "Vårdnadshavare grundskola åk 1-9",
    "vardnadshavare-anpassad-grundskola": "Vårdnadshavare anpassad grundskola",
    "pedagogisk-personal-forskola": "Pedagogisk personal förskola",
    "vardnadshavare-forskola": "Vårdnadshavare förskola",
}

# Skolenkäten index categories (themes measured in the survey)
SKOLENKATEN_INDEX = {
    "information": "Information om utbildningen",
    "stimulans": "Stimulans",
    "stod": "Stöd",
    "kritiskt-tankande": "Kritiskt tänkande",
    "bemotande-larare": "Bemötande - lärare",
    "bemotande-elever": "Bemötande - elever",
    "inflytande": "Inflytande",
    "studiero": "Studiero",
    "trygghet": "Trygghet",
    "forhindra-krankningar": "Förhindra kränkningar",
    "elevhalsa": "Elevhälsa",
    "nojdhet": "Övergripande nöjdhet",
}

# Tillstånd decision types
TILLSTAND_BESLUT_TYPES = {
    "godkannande": "Godkännande",
    "avslag": "Avslag",
    "avskrivning": "Avskrivning",
    "delvis-godkannande": "Delvis godkännande",
}

# Tillstånd application types
TILLSTAND_ANSOKNINGSTYPER = {
    "nyetablering": "Nyetablering",
    "utokning": "Utökning",
}

# Tillstånd school forms
TILLSTAND_SKOLFORMER = {
    "grundskola": "Grundskola",
    "gymnasieskola": "Gymnasieskola",
    "internationell-skola": "Internationell skola",
    "forskoleklass": "Förskoleklass",
    "fritidshem": "Fritidshem",
    "anpassad-grundskola": "Anpassad grundskola",
    "anpassad-gymnasieskola": "Anpassad gymnasieskola",
}


class TillstandSummary(BaseModel):
    """Summary statistics for tillståndsbeslut."""

    year: int
    skolstart_lasar: str
    total_decisions: int = 0
    godkannanden: int = 0
    avslag: int = 0
    avskrivningar: int = 0

    # By application type
    nyetableringar_total: int = 0
    nyetableringar_godkanda: int = 0
    utokningar_total: int = 0
    utokningar_godkanda: int = 0

    # By school form
    by_skolform: dict[str, dict[str, int]] = {}


# =============================================================================
# TILLSYN STATISTICS MODELS (Viten, TUI, Planerad Tillsyn)
# =============================================================================


class ViteStatistik(BaseModel):
    """Fine (vite) statistics for a single year."""

    year: int
    beslut_totalt: int = 0
    beslut_enskild: int = 0
    beslut_offentlig: int = 0
    ansokningar_totalt: int = 0
    ansokningar_enskild: int = 0
    ansokningar_offentlig: int = 0


class TUIStatistik(BaseModel):
    """Tillsyn Utifran Individärenden (TUI) statistics - BEO-related."""

    year: int

    # Overall decision counts
    beslut_totalt: int = 0
    beslut_med_brist: int = 0
    andel_med_brist: Optional[float] = None

    # By principal type
    beslut_enskild: int = 0
    beslut_enskild_med_brist: int = 0
    beslut_offentlig: int = 0
    beslut_offentlig_med_brist: int = 0

    # By gender
    beslut_flickor: int = 0
    beslut_pojkar: int = 0
    beslut_ovriga: int = 0

    # By school form (verksamhetsform)
    by_skolform: dict[str, int] = {}

    # By assessment area (bedömningsområde)
    brister_krankande_behandling: int = 0
    brister_elev_elev: int = 0
    brister_personal_elev: int = 0
    brister_stod: int = 0
    brister_undervisning: int = 0
    brister_ovriga: int = 0


class PlaneradTillsynStatistik(BaseModel):
    """Planned supervision (planerad tillsyn) statistics."""

    year: int
    beslut_totalt: int = 0
    beslut_med_brist: int = 0
    andel_med_brist: Optional[float] = None

    # By principal type
    beslut_enskild: int = 0
    beslut_enskild_med_brist: int = 0
    beslut_offentlig: int = 0
    beslut_offentlig_med_brist: int = 0

    # By school form
    by_skolform: dict[str, dict[str, int]] = {}  # skolform -> {total, med_brist}


class TillsynStatistikSummary(BaseModel):
    """Combined summary of all Tillsyn statistics."""

    viten: list[ViteStatistik] = Field(default_factory=list)
    tui: list[TUIStatistik] = Field(default_factory=list)
    planerad_tillsyn: list[PlaneradTillsynStatistik] = Field(default_factory=list)
    years_available: list[int] = Field(default_factory=list)


# Tillsyn statistics categories
TILLSYN_CATEGORIES = {
    "viten": "Viten (fines)",
    "tui": "Tillsyn utifran individärenden (TUI/BEO)",
    "planerad-tillsyn": "Planerad tillsyn",
    "riktad-tillsyn": "Riktad tillsyn",
    "regelbunden-tillsyn": "Regelbunden tillsyn",
    "kvalitetsgranskning": "Kvalitetsgranskning",
}

# TUI/BEO assessment areas
TUI_ASSESSMENT_AREAS = {
    "krankande-behandling": "Kränkande behandling",
    "elev-elev": "Kränkning elev-elev",
    "personal-elev": "Kränkning personal-elev",
    "stod": "Stöd / Särskilt stöd",
    "undervisning": "Undervisning / Särskild undervisning",
    "disciplinara-atgarder": "Disciplinära åtgärder",
    "skolplikt": "Skolplikt och rätt till utbildning",
    "ovriga": "Övriga brister",
}


# =============================================================================
# OMBEDÖMNING NATIONELLA PROV MODELS
# =============================================================================


class OmbedomningRapport(BaseModel):
    """A report about re-evaluation of national tests (Ombedömning nationella prov)."""

    title: str
    year: int  # Publication year
    test_year: Optional[int] = None  # Year of the tests being evaluated
    omgang: Optional[int] = None  # Round number (omgång 1-10)
    filename: str
    url: str  # Full URL to PDF on skolinspektionen.se
    local_path: Optional[str] = None  # Local path if downloaded
    description: Optional[str] = None
    subjects: list[str] = Field(default_factory=list)  # Tested subjects
    grades: list[str] = Field(default_factory=list)  # Grade levels (åk 3, 6, 9, gy)


class OmbedomningSummary(BaseModel):
    """Summary of available ombedömning reports."""

    total_reports: int = 0
    years_available: list[int] = Field(default_factory=list)
    latest_report: Optional[OmbedomningRapport] = None
    subjects_covered: list[str] = Field(default_factory=list)
