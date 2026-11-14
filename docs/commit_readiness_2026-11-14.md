# Valmis commit-kokonaisuus — 14.11.2026

## Päätös ja rajaus

Julkisten tiedostojen katselmoinnissa ja täydellisissä offline-testeissä ei löytynyt estävää sovellusvirhettä tai todellista salaisuutta. Alkuperäinen 42 tiedoston indeksi oli vanhempi kuin testattu työpuu. Se on nyt täydennetty täsmälleen alla luetelluiksi 50 julkiseksi tiedostoksi, ja lopputarkistus vahvisti indeksin vastaavan testattua työpuuta. FI-fixturen rikkinäiset merkit on korjattu merkitystä muuttamatta. Commitia, pushia tai mergeä ei tehty.

Kokonaisuus sisältää alkuperäiset 42 tiedostoa uusimpine työpuuversioineen, `requirements.txt` sekä seitsemän aiemmin untracked-tiedostoa. Yksityisiä benchmarkeja, generoitua ajonaikaista aineistoa tai tietokantaa ei lisätä. Tämä on testattu engineering-kokonaisuus, ei näyttö Mistralin tuotantoskeemojen live-hyväksynnästä tai uuden kehotteen laadullisesta paremmuudesta. Omistaja voi tehdä commitin tarkistettuaan tämän kokonaisuuden.

Ehdotettu commit-otsikko: `Complete workflow navigation and harden Mistral integration`.

Ehdotettu kuvaus: nelivaiheinen FI/EN-navigointi ja Draft & Review -viimeistely, turvallinen Mistral-transportti ja diagnostiikka, rajattu yhden pyynnön yhteystesti, offline-verkkosuoja sekä fiktiivinen suunnittelulaadun arviointikehys. Qwen säilyy paikallisena oletuksena. Mistral Large 4 -yhteyden onnistuminen on omistajan raportoima; tuotannon skeematuen, luotettavuuden ja laatuhyödyn live-varmennus jää avoimeksi.

## Testit ja toiminnallinen säilyminen

Täydellinen **työpuun** offline-ajo:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
```

Ympäristö: `PYTHONDONTWRITEBYTECODE=1`, `HANKELUOTSI_LIVE_FUNDING=0` ja yksilöllinen väliaikainen `HANKELUOTSI_DB_PATH`. Uusin korjatun fixturen ja kahden uuden regressiotapauksen täydellinen ajo: **896 passed, 2 skipped in 53.22s**. Ohitukset ovat opt-in-verkolliset julkisten rahoituslähteiden testit. Ei Mistral-, Qwen- tai mallilista-API-kutsuja. Testien socket-suoja estää ulkoiset yhteydet; HTTPTransport/httpcore2/H11-koodekkitesteissä liikenne pysyy muistissa. `python -m pip check`: **No broken requirements found**. Molemmat Git-diff-tarkistukset läpäisevät; mahdolliset LF/CRLF-ilmoitukset eivät ole tarkistusvirheitä. Edellisen katselmoinnin 894/2 jää historialliseksi tulokseksi.

Koko sarja kattaa paikallisen Qwen-sovittimen, validoinnin, tallennuksen, FI/EN-navigoinnin ja lomaketilan, suostumukset, Draft & Review -tilasiirtymät, stale-write-suojan, hyväksynnän lukituksen sekä viennin. FI/EN-Mistral-työnkulkutesti tarkistaa mallin `mistral-large-4` ja fiktiivisen Bearer-avaimen kolmesta varsinaisella sovittimella muodostetusta mock-pyynnöstä.

Paikallinen oletus pysyy `qwen3.5-4b`:nä; `llm_client.py`:n muutos lisää vain valinnaista tulosmetatietoa. Konfiguraatio, repository, skeemat ja exporter-moduulit eivät muutu HEADista. Mistral ei korvaa paikallista mallia automaattisesti. Molemmat polut tarvitsevat myöhemmin omat live-laadun mittaukset; tässä ei ajettu uutta oikeaa mallia tai selaindemoa. Käynnissä olevan Streamlit-prosessin avainta ei tarkastettu.

Commit sisältää myös aiemmin tehtyjä kehoteversioiden muutoksia: `concept_v2`, `draft_workflow_v2`, `review_workflow_v3`. Niitä ei pidä kuvata pelkäksi autentikointikorjaukseksi tai osoitetuksi laatuhyödyksi. Vanhat kehote-/benchmark-aineistot säilyvät.

## Salaisuudet ja yksityiset aineistot

Tarkistettiin kaikki 42 indeksitiedostoa kokonaisina, kaikki tracked-työpuutiedostot ja julkaisuehdotuksen untracked-tiedostot. Rajattu automaattinen sisältö- ja tiedostonimiskannaus etsii tavallisia avain-/token-/private-key-muotoja, salaisuuksien literaaliasetuksia, tunnuksellisia URL-osoitteita, tunnetun nykyisen ympäristöavaimen tarkkaa osumaa, kiellettyjä tiedostotyyppejä ja konfliktimerkkejä. Tuloste ei paljasta mahdollisia osumatekstejä. Yhdeksän pattern-osumaa käytiin läpi: ne ovat fiktiivisiä testitunnuksia, kielteisten testien URL-esimerkkejä tai synteettisten response-otsakkeiden sisältöjä. Todellisia avaimia, konfliktimerkkejä tai kiellettyjä tracked-/ehdokastiedostoja ei löytynyt. Tämä on rajattu katselmointi, ei lupaus kaikkien mahdollisten salaisuusmuotojen tunnistamisesta tai Git-historian auditointi.

**Pidettävä yksityisenä; ei lisätä commitiin:**

- `.env` ja muut `.env.*`-tiedostot paitsi turvallinen `.env.example`; `.streamlit/secrets.toml` ja oikeat avain-/sertifikaattitiedostot.
- `hankeluotsi.sqlite3`, kaikki `*.db`, `*.db-*`, `*.sqlite*` sekä mahdolliset journal/WAL/SHM-tiedostot.
- Koko `.benchmark-private/`: raakamallivastaukset, diagnostiikka, paikalliset benchmark-ajot, selaimen kuvakaappaukset ja lokit, väliaikaiset työkaluskriptit.
- `benchmark-results/qwen-mistral-five-2026-11-12/blind/PRIVATE-model-map.json` ja kaikki `**/PRIVATE-*.json`.
- `benchmark-results/qwen-mistral-five-2026-11-12/local-model-metadata.json` ja raaka runtime-/provider-aineisto.
- `.venv/`, Python-/pytest-välimuistit sekä väliaikaiset lokit ja muut ajotiedostot.

Nykyinen `.gitignore` suojaa olemassa olevat yksityiset aineistot. Yllä mainitut oikeat paikalliset tietokanta-, kartta- ja runtime-tiedostot eivät ole tracked/staged. Niiden sisältöjä tai avainarvoja ei tulostettu. Lähdekoodin merkkijono `PRIVATE-model-map.json` on tiedostonimeä käsittelevää julkista koodia, ei varsinainen mallikartta.

Gitissä on jo **64 historiallista benchmark-tiedostoa**, joihin tämä työ ei tee muutoksia. Niitä ei poisteta tai blanket-untrackata; yksityiset kartat ja paikallinen runtime-metadata ovat erikseen ignore-suojattuja. Uusia ajotuloksia, raakavastauksia, karttoja tai human-pisteitä ei ehdoteta lisättäviksi. Julkisten raporttien omistajan live-havainto 26/32/58 tokenia ja noin 1,45 s on merkitty omistajan ilmoittamaksi; tuntematonta alkuperäistä HTTP-statusta, finish reasonia tai laskutusta ei keksitä.

## FI-fixturen merkkikorjaus ja toistettavuus

`tests/fixtures/planning_quality_cases_v1.json`: korjattu 22 erilaista rikkinäistä suomenkielistä ilmausta P02/P04-tapauksista sekä P04:n päivämäärävälin erotin. Yhteensä 53 merkkijonoarvoa muuttui. Rekursiivinen ennen/jälkeen-vertailu vahvisti, että jokainen muutos on samanpituinen `?` → `ä/ö/Ä/Ö/–` -merkkikorvaus; avaimet, listat, numerot, ID:t ja molemmat englanninkieliset tapausoliot pysyivät identtisinä. Oikeat loppukysymysmerkit, tarkoituksella heikot vaikutusväitteet, toistuvat kumppanit ja vuoden 2024 päivämäärät säilyivät. Korjaus ei paranna tarkoituksella heikkoja kontrolleja.

Kaksi parametrisoitua regressiotapausta käy rekursiivisesti läpi kummankin FI-tapauksen tekstiarvot, estää inline-kysymysmerkkikorruption ja korvaus-/mojibake-merkit sekä varmistaa oikean UTF-8-tekstin ja kysymysmerkit. Korjatun tiedoston SHA-256: `7606073d2636036a5e8f9c5bcc5b1267267a79a6b86872bcb450823cdfa79c7d`. Tietomuoto säilyy `planning_cases_v1`:nä; vain lähdesisältö korjautui. `create_plan` sisällyttää lähdehashit ja kanoniset syötteet, joten korjatulle aineistolle pitää muodostaa uusi manifesti. `verify_plan` ei hyväksy vanhaa lähdehashia uuden tutkimuksen tiedoiksi. Vanhoja manifesteja, tuloksia tai sokkokarttoja ei kirjoitettu uudelleen. Alkuperäisestä fixturestä ja indeksistä otettiin yksityiset paikalliset kopiot ignore-suojattuun `.benchmark-private/`-hakemistoon. Merkkitesti ei ole ihmisen tekemä ammatillisen laadun arvio.

Hashin rivinvaihtorajaus: yllä oleva `760607…` on tämän Windows-työpuun raakatiedoston CRLF-hash. Git-indeksin LF-normalisoidun fixture-blobin SHA-256 on `3e1868bf4735f96f3a77278c63fa4d6ec5c47ec1b7a49690b376bf9ae4b3e44b`. JSON-sisältö on sama; indeksin vastaavuus tarkoittaa Gitin normaalia rivinvaihtosuodatettua vastaavuutta. Raakatiedostoihin perustuvat manifestit pitää muodostaa ja todentaa samassa tallennetussa lähde-/rivinvaihtoympäristössä, eikä eri ympäristöjen hash-arvoja saa esittää samoina.

## Tarkka julkinen tiedostoehdotus

Merkintä **S** tarkoittaa lopulliseen indeksiin sisältyvää tarkistettua työpuuversiota. Kaikki 50 polkua lisättiin eksplisiittisesti nimettyinä, ei `git add .` -komennolla. Indeksin ja työpuun vastaavuus sekä tiedostolista tarkistettiin. Tämä ei luonut commitia.

| Sovellus / konfiguraatio (15) | Tila |
| --- | --- |
| `app.py` | S |
| `assets/styles.css` | S |
| `hankeluotsi/draft_ui.py` | S |
| `hankeluotsi/draft_workflow.py` | S |
| `hankeluotsi/i18n.py` | S |
| `hankeluotsi/llm_client.py` | S |
| `hankeluotsi/mistral_client.py` | S |
| `hankeluotsi/mistral_smoke.py` | S |
| `hankeluotsi/planning_benchmark.py` | S |
| `hankeluotsi/planning_experiments.py` | S |
| `hankeluotsi/planning_quality.py` | S |
| `hankeluotsi/presentation.py` | S |
| `hankeluotsi/prompts.py` | S |
| `hankeluotsi/workflow_navigation.py` | S |
| `requirements.txt` | S |

| Testit ja fiktiiviset fixturet (21) | Tila |
| --- | --- |
| `tests/fixtures/planning_quality_cases_v1.json` | S |
| `tests/fixtures/planning_rubric_v1.json` | S |
| `tests/test_benchmark.py` | S |
| `tests/test_draft_ui.py` | S |
| `tests/test_draft_workflow.py` | S |
| `tests/test_i18n.py` | S |
| `tests/test_llm_client.py` | S |
| `tests/test_mistral.py` | S |
| `tests/test_mistral_smoke.py` | S |
| `tests/test_mistral_workflow.py` | S |
| `tests/test_model_quality.py` | S |
| `tests/test_navigation.py` | S |
| `tests/test_planning_benchmark.py` | S |
| `tests/test_planning_experiments.py` | S |
| `tests/test_planning_quality.py` | S |
| `tests/test_presentation.py` | S |
| `tests/test_startup_imports.py` | S |
| `tests/conftest.py` | S |
| `tests/test_mistral_schema_contract.py` | S |
| `tests/test_mistral_transport_safety.py` | S |
| `tests/test_offline_network_guard.py` | S |

| Dokumentaatio (14) | Tila |
| --- | --- |
| `PLANS.md` | S |
| `README.md` | S |
| `docs/development_log.md` | S |
| `docs/draft_review.md` | S |
| `docs/mistral_diagnosis.md` | S |
| `docs/mistral_readiness.md` | S |
| `docs/mistral_setup.md` | S |
| `docs/model_comparison_plan.md` | S |
| `docs/planning_quality_experiments.md` | S |
| `docs/startup_troubleshooting.md` | S |
| `docs/workflow_navigation.md` | S |
| `docs/mistral_connectivity_2026-11-14.md` | S |
| `docs/overnight_engineering_2026-11-13.md` | S |
| `docs/commit_readiness_2026-11-14.md` | S |

## Commitin tekeminen

Omistaja voi tarkistaa lopullisen `git diff --cached` -sisällön ja tehdä commitin suositellulla otsikolla. Valmistelussa ei tehdä commitia, pushia, mergeä, resetiä, stashia tai poistoja. Yksityiset tiedostot ja alkuperäinen näyttö jäävät paikallisiksi. Toiminnallisuus on varmennettu offline-sovitinten ja käyttöliittymätestien tasolla; uutta oikean mallin tai selaimen testiä ei tehty.

Historiallinen edellinen katselmointi päättyi tilaan 42 staged / 12 unstaged tracked / 7 untracked ja säilytti indeksin ennallaan. Tämä viimeistely korjaa FI-fixturen, lisää kaksi testitapausta ja päivittää suunnitelman/lokin/tämän raportin sekä kokoaa kaikki 50 polkua indeksiin. Lopputarkistus dokumentoidaan kehityslokiin; haara ja HEAD säilyvät, indeksi päivitetään tarkoituksella. Aiemman katselmoinnin 336 tiedoston säilymishavainnot ja yksityiset näyttötiedostot säilyvät historiallisena tietona lokissa.

**Lopputulos:** 50 staged / 0 unstaged / 0 julkista untracked-tiedostoa. Staged-polut vastaavat täsmälleen tämän raportin 50 polkua ja `git diff --quiet` vahvistaa työpuun vastaavan indeksiä. `git diff --check` ja `git diff --cached --check` läpäisevät. Lopullisten indeksiblobien salaisuusskannauksen kolme osumaa ovat jo tarkistettuja synteettisiä testiarvoja, ei oikeita tunnuksia. Ei kiellettyjä tracked-tiedostoja tai konfliktimerkkejä. Aloituksen 337 tiedostosta 332 pysyi byte-identtisenä; vain fixture/testi/raportti/PLANS/loki muuttuivat, ei puuttuvia tiedostoja. Viisi uutta paikallista varmuuskopiota ovat ignore-suojattuja. Alkuperäisen indeksin ja fixturen kopiot vastaavat aloituksen sormenjälkiä. Haara `feature/mistral-integration` ja HEAD ovat ennallaan. Valmis omistajan committia varten, ilman uusia live-testejä tai laatuväitteitä.
