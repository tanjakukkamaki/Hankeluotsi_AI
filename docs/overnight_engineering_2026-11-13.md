# HankeLuotsi AI: offline-tutkimus ja prototyypin varmennus

Päivä: **13.11.2026**, Suomen aika. Haara: `feature/mistral-integration`.

Työ perustuu omistajan Autonomous Overnight Engineering Task -liitteeseen. Agentti ei tehnyt yhtään live-Mistral-, mallilista-, paikallisen mallin tai muun palveluntarjoajan API-kutsua. Vain julkista teknistä dokumentaatiota luettiin. Maksullisia generointeja, commitia, pushia, mergeä, stage-muutoksia tai oikeiden projektien muutoksia ei tehty. Omistajan työtunteja ei ole ilmoitettu eikä niitä päätellä testien kestosta.

## 1. Johtopäätös ja vahvistetut löydökset

**Aiemman HTTP400:n tarkkaa palvelinpuolen juurisyytä ei voi vahvistaa offline.** Omistaja ilmoitti kolme generoinnin400-virhettä tunnisteilla `mistral-large-latest`/`mistral-large-4` sekä yhden mallilista-GET:n400-virheen. Aiemmat virherungot/metatiedot eivät ole käytettävissä; havaintoja ei toistettu eikä puuttuvia viestejä keksitty.

GET `/v1/models` ei lähetä mallia, messages-listaa, max_tokens-arvoa tai JSON-skeemaa. Minimaalinen POST ei lähetä skeemaa. Siksi Pydantic-skeema, viestisisältö tai32-tokenin raja **eivät voi olla kaikkien ilmoitettujen epäonnistumisten yhteinen selitys**.

Vahvistetut ohjelmistolöydökset:

1. Mallilistauksen suppea kolmen kentän tuloste jätti virheen tarkat tiedot pois. Tuotannon POST oli jo korjattu säilyttämään suodatetut virheet, mutta GET:ssä tämä tieto ei ollut saatavilla. Suppea tuloste säilytettiin; uusi valinnainen `--models --diagnostics` välittää suodatuksen ja metatiedot **samasta yhdestä GET:stä**.
2. `Client(trust_env=False)` ei ohjaa erikseen luodun `HTTPTransport`-olion omaa `trust_env=True`-oletusta. TLS-varmenneympäristö saattoi siis vaikuttaa yhteyteen vastoin tarkoitettua eristystä. Kolmessa Mistral-polussa transportille annetaan nyt myös `trust_env=False`. Varmennetarkistus säilyy: CERT_REQUIRED ja hostname-tarkistus päällä. Tämä on todennettu asetusepäjohdonmukaisuus, **ei todiste400:n syystä**; varmennevirhe aiheuttaa tavallisesti yhteys-/TLS-virheen.
3. Suodatin ei käsitellyt kaikkia `detail`-merkkijonon tai `error`-merkkijonon muotoja eikä kertonut selvästi, mitä kenttiä oli peitetty. Muodot tunnistetaan nyt rajatusti ja tuloste kertoo peitetyt kenttänimet, rungon muodon ja riittääkö tieto syyluokan tunnistamiseen.
4. Tavallisessa pytest-ajossa ei ollut yhteistä verkkosuojaa. Uusi testifixture estää DNS:n, HTTP-yhteyden luonnin, suorat TCP-connect/connect_ex-kutsut ja UDP-sendto:n. Windowsin stdlib-socketpairin paikallinen asyncio-heräte sallitaan vain socketpairin oman luomisen aikana; esimerkiksi suora localhost:1234-yhteys estyy. Ainoa aiempi verkkotestipoikkeus on erikseen `HANKELUOTSI_LIVE_FUNDING=1`-valinnalla sallittava julkisten rahoituslähteiden integraatiotesti. Tässä työssä se oli pois päältä. Smoke-aliprosessitesti asentaa oman suojansa ennen moduulin tuontia.

## 2. Pyynnöt ja kuljetuksen vertailu

| Tarkistus | Todennettu nykyisestä toteutuksesta ja offline-testeistä |
| --- | --- |
| Mallilista | GET `https://api.mistral.ai/v1/models`, yksi Bearer-otsake; ei runkoa, queryä tai Content-Type-vaatimusta |
| Minimaalinen smoke | POST `/v1/chat/completions`; vain model/messages/max_tokens32/stream=false, yksi fiktiivinen user-viesti, ei skeemaa |
| Tuotannon konsepti/luonnos/arvio | Sama POST; system+user, temperature0.2, vaihekohtaiset tokenrajat, json_schema-vastemuoto |
| Serialisointi | application/json POST:ssa, oikea Host/polku, yksi Bearer-otsake, UTF-8 ja tavumääräinen Content-Length |
| Uusinnat / redirectit | Mistralissa retries0, follow_redirects=False; ei automaattista fallbackia |
| Proxy / TLS | Client- ja transport-tason trust_env=False; ei ympäristöproxy-reittejä; TLS-tarkistusta ei poistettu |
| Paikallinen vertailureitti | OpenAI SDK:n oletukset eroavat: retries2, redirectit sallittu, Accept application/json ja SDK:n User-Agent. Suora httpx2 käyttää eri oletusotsakkeita. Paikallista reittiä ei muutettu. |

MockTransport-tarkistuksen lisäksi **oikea httpx2.HTTPTransport → httpcore2 → H11** ajoi HTTP/1.1-koodauksen muistissa toimivaan backend/streamiin. Synteettinen400-vastaus käsiteltiin takaisin turvalliseksi diagnostiikaksi. Virtuaaliyhteys käytti oikeaa Hostia/SNI:tä, mutta `start_tls` oli testiobjekti: **ei socketia, DNS:ää, salausta tai oikeaa TLS-kättelyä**. Tämä osoittaa offline-koodauksen toiminnan, ei ulkoisen palvelun tai verkon yhteensopivuutta.

Varmennettu ympäristö: Python3.12.0, OpenAI3.6.0, httpx2/httpcore2 2.16.0, Pydantic2.13.5, OpenSSL3.0.11. Suorat riippuvuudet on jo ilmoitettu requirements.txt:ssä; `pip check` läpäisi. Paketteja tai teknologiapinoa ei vaihdettu.

Viralliset vertailulähteet: [Models API](https://docs.mistral.ai/api/endpoint/models), [Chat Completions](https://docs.mistral.ai/api/endpoint/chat), [virhesopimus](https://docs.mistral.ai/resources/error-glossary). Dokumentaation max_tokens on kokonaisluku, stream boolean, ja input+ulostuloraja ei saa ylittää kontekstia.32 tokenille ei löytynyt yleistä kieltoa. Accept `*/*` verrattuna SDK:n application/json-oletukseen on todettu ero, ei osoitettu virhe; sitä tai muita valideja API-parametreja ei vaihdettu arvauksella.

## 3. Jäljelle jäävät selitykset näytön perusteella

| Tutkittava ryhmä | Näyttö ja epävarmuus |
| --- | --- |
| 1. Yhteinen avain-/työtila-/palvelimen pyyntökonteksti | Sopii sekä GET:n että POST:n epäonnistumiseen. Avaimen aktiivisuutta, inference-oikeutta, työtilaa, saldoa tai tilin rajoituksia ei ole vahvistettu.400 ei todista puuttuvaa käyttöoikeutta tai laskutusvikaa. |
| 2. Palvelun reuna/välittävä verkko tai kuljetuksen toimintaympäristö | Sopii molempiin päätepisteisiin, mutta aiempien vastausten MIME/HTTP/metatiedot puuttuvat. HTML400 tukisi välittäjän/reunapalvelun tutkimista; sitä ei ole oikeasti havaittu. Sovelluksen ympäristöproxy on pois käytöstä, mutta ulkoista verkkoa ei voi todentaa offline. |
| 3. TLS-ympäristöasetusten vahvistettu epäjohdonmukaisuus | Korjattu ja testattu, mutta heikko suora selitys HTTP400:lle. Ei väitetä ratkaisuksi aiempaan palvelinvirheeseen. |
| Mallikohtainen POST-rajoitus | Saattaa myöhemmin koskea generointia, mutta ei selitä mallilista-GET:n400:aa. Myös latest-alias voi osoittaa samaan Large4-perheeseen. |
| Pydantic-skeema /32 tokenia yhteisenä syynä | Ei sovi GET:hen; skeemaa ei ole myöskään minimaalisessa POST:ssa. Varsinaisen luonnosskeeman palvelinhyväksyntä on erillinen avoin asia. |

Taulukko on tutkimisjärjestys ja selitysten kattavuus, ei todennäköisyysmittaus. Omistajan todellista API-avainta tai sen muotoa ei luettu toisesta prosessista. Uudet paikalliset key_shape_flags-liput voivat myöhemmin näyttää Bearer-etuliitteen, ylimääräisten lainausmerkkien, sisäisen whitespace-merkin tai ei-ASCII-merkin epäilyn ilman avainta/pituutta; ne eivät varmista avaimen kelpoisuutta.

## 4. Turvallinen diagnostiikka

Jaettu parseri säilyttää HTTP-statuksen, sallitun provider-koodin, parametrin, enintään240-merkkisen suodatetun viestin, havaintoperusteen ja seuraavan toimintaohjeen.64KiB:n virherungon parsintaraja on puskuroidun vastauksen raja, ei verkkolatauksen muistiraja. Tunnistamattomia vapaita arvoja ei julkaista; `withheld_fields` kertoo vain peitettyjen kenttien nimet. `body_format` erottaa JSON-olion, muun JSONin, ei-JSONin ja liian suuren rungon; `diagnostic_information=insufficient` kertoo, ettei syytä voitu tunnistaa.

Vastausmetatiedoissa sallitaan vain tunnettu MIME-/HTTP-versioluokka, puskuroidun rungon tavumäärä ja tieto request-id-/Location-/WWW-Authenticate-otsakkeen läsnäolosta. Otsakkeiden arvoja, redirect-osoitetta, request-id:tä, palvelinbanneria tai raakaa HTML-/JSON-rungon tekstiä ei tulosteta. Peitetty viesti on rekonstruoitu turvallinen yhteenveto, ei alkuperäisen viestin sanatarkka kopio.

`--models` säilyttää aiemmat kolme kenttää. Valinnainen `--diagnostics` lisää tietoa saman pyynnön virheestä tai onnistumisen turvallisista metatiedoista; se ei tee lisäpyyntöä. Ilman `--models`-valintaa `--diagnostics` pysähtyy ennen verkkokutsua. Puuttuva avain, timeout, yhteysvirhe ja HTTP200:n epäkelpo listaus saavat selkeän turvallisen jatko-ohjeen. null-lista ei muutu false-poissaoloksi. `actual_billed_cost=null` on edelleen tuntematon, ei nollahinta.

## 5. Pydantic-skeemat ja sisällön laatu erillisinä asioina

| Lähetetty malli | Pakolliset kentät / juuren kentät | Tarkistetut ominaisuudet |
| --- | --- | --- |
| ConceptPaper | 6/9 | oletusarvoiset schema_version/assumptions/open_questions säilyvät |
| ApplicationDraft | 18/20 | schema_version ja nullable generation_metadata oletusarvoisia |
| ReviewSelection | 5/7 | sama metadata-/versioperiaate; lähdevalitsimet erotetaan tallennetusta ReviewReportista |

Kaikki paikalliset `$ref`-viittaukset ratkeavat ja juuren/sisäkkäisten objektien additionalProperties=false säilyy. Vastemuoto on json_schema ja schema on oikeassa wire-kentässä. [Mistralin ohje](https://docs.mistral.ai/inference/conversations/structured-output/custom) ja [virallinen SDK-malli](https://raw.githubusercontent.com/mistralai/client-python/main/src/mistralai/client/models/jsonschema.py) eivät osoita optional strict -kentän pois jättämistä virheeksi. Toisen API:n all-required/strict-sääntöjä ei kopioitu tähän. Projektiskeemoja tai kehotteita ei muutettu. Live-hyväksyntää ei väitetä.

Cloud-polku edellyttää edelleen stop-valmistumista, JSONia ja Pydantic-validointia. Katkennut/tyhjä/epäkelpo tulos ei korvaa viimeistä validia projektia. Luonnoksen4096/arvion2048 tokenin rajat säilyvät. Paikallinen Qwen-reitti pysyy ennallaan.

Vuoden2025 aikataulu havaitaan vertailupäivällä13.11.2026 varoituksena. Toistuvat/otsikoidut kumppaninimet havaitaan normalisoinnin jälkeen. Nämä ovat ohjeellisia havaintoja, eivät uusia hyväksynnän estäviä sääntöjä, eivätkä muuta hyväksyttyä vientiä. Roolitekstin mielivaltaisia toistoja ei yleisesti tunnisteta.

Yksi työpaketti ja kahden päivän työpaja voivat olla rajattu pilotti. Laajan alueellisen vaikutuksen uskottavuus, mittarin operatiivisuus ja toiminta→tulos→vaikutus-ketjun merkitys eivät ratkea ID-viitteistä. Istutetut heikot P03/P04-suunnitelmat voivat läpäistä rakennegraafin ja silti olla ammatillisesti heikkoja. Nykyiset draft_v2/review_v3-kehotteet ohjaavat arvioimaan näitä; niiden todellinen onnistuminen vaatii AI-avusteisen arvion erottamista riippumattomasta ihmisarviosta. Ihmispisteitä ei täytetty. Tässä ei tehty uutta mallilaadun koetta.

## 6. Testitulokset ja demonstraatiovalmius

- Kohdennettu Mistral-/kuljetus-/skeema-/verkkosuoja-/navigointiajo: **252 passed,8.37s**.
- Koko lopullinen offline-sarja: **871 passed,2 skipped,52.45s**.
- Komento: `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider`; live-rahoitushaku pois, bytecode/cache-kirjoitus pois ja uusi väliaikainen oletus-SQLite.
- Ohitukset ovat kaksi erikseen sallittavaa julkisen rahoitustiedon verkkotestiä, eivät peitettyjä Mistral-virheitä.
- `python -m pip check`: No broken requirements found.
- `git diff --check` ja `git diff --cached --check` läpäisivät; vain LF/CRLF-ilmoituksia. Alkuperäisistä180 tiedostosta173 säilyi tavutasolla,7 muuttui sovitussa laajuudessa;5 uutta julkista testi-/raporttitiedostoa. HEAD/haara/indeksin fingerprint säilyivät. Puuttuvia alkuperäisiä tiedostoja ei ole.

Sarja kattaa FI/EN-navigoinnin, keskeneräisen syötteen/projektivalinnan säilymisen, toistuvat rerunit ilman pilvikutsua, eksplisiittisen suostumuksen/hyväksynnän, lukitun hyväksytyn projektin, CAS-/tilasiirtymät, regeneraation atomisen invalidoinnin, Markdown-viennin ja nykyisen PDF-viennin testit. UI-/repository-/PDF-koodia ei muutettu.

**HAMK-demoon:** paikalliseen käyttöön fiktiivisillä tiedoilla tarkoitettu prototyyppi on näiden offline-regressioiden perusteella edelleen tarkistettavissa/demonstroitavissa. Omistaja on aiemmin ilmoittanut paikallisen Qwen-kokonaisketjun toimivaksi. Tässä työssä ei tehty uutta live-Qwen- tai selaindemoa eikä arvioitu nykyisen LM Studio -mallin saatavuutta. Ennen esitystä omistaja varmistaa paikallisen mallin ja käy tutun fiktiivisen demon läpi. Mistralia ei pidä esittää toimivaksi; ammatillinen teksti tarvitsee ihmisen tarkistuksen.

## 7. Git ja muuttuneet tiedostot

Aloitustilassa oli **42 stageattua tiedostoa**:14 lähde-/asset-tiedostoa,17 testi-/fixture-tiedostoa ja11 dokumenttia. Lisäksi oli **11 unstaged-tiedostoa**:2 lähdekoodia,3 testitiedostoa,5 dokumenttia ja requirements.txt. Näitä kerroksia tarkasteltiin erikseen. Indeksiin ei koskettu. Pelkkä nykyinen stage ei sisällä kaikkia testattuja työpuun kuljetuskorjauksia/riippuvuuksia; työpuun testituloksia ei esitetä staged-only-snapshotin testinä.

Lopputarkistus: edelleen42 stageattua ja11 unstaged-seurattua tiedostoa sekä5 uutta untracked-testi-/raporttitiedostoa. Indeksi/HEAD/haara ennallaan. Stage- ja unstaged-kuviotarkistukset sekä uusien tiedostojen kuviotarkistus läpäisivät; seurannassa ei ole yksityisiä runtime-/tietokanta-/mallikarttatiedostoja.

Tämän tehtävän toteutusmuutokset:

| Tiedosto | Tarkoitus |
| --- | --- |
| hankeluotsi/mistral_client.py | TLS trust_env -korjaus, rajatut detail/error-muodot, turvallinen vastausmetadata ja näkyvät suodatusrajat |
| hankeluotsi/mistral_smoke.py | sama TLS-korjaus, vapaaehtoinen GET-virhediagnostiikka, paikalliset key-/ympäristöliput |
| tests/test_mistral.py | metatieto-/detail-/mallitunnisteregressiot ja uusi transport-sopimus |
| tests/test_mistral_smoke.py | valinnainen GET-diagnoosi, muotoliput, ei salaisuuksia/lisäpyyntöjä; suojattu lapsiprosessi |
| tests/conftest.py | oletusarvoinen DNS/TCP/UDP-verkkosuoja |
| tests/test_offline_network_guard.py | suojan fail-closed- ja sallittu socketpair-regressio |
| tests/test_mistral_transport_safety.py | SSL/proxy/SDK-erot sekä MockTransport- ja täysin muistissa toimiva H11-kooderitesti |
| tests/test_mistral_schema_contract.py | oikeat ulosmenevät skeemat ja vuoden2025 read-only-varoitus |
| docs/mistral_readiness.md | uusi vain offline -seuraava askel ja myöhemmin erikseen sallittava GET-diagnostiikka |
| docs/overnight_engineering_2026-11-13.md | tämä raportti |
| PLANS.md, docs/development_log.md | toteutunut laajuus, testit ja rajat |

Stage-/unstaged-tekstien erilliset salaisuuskuvioiden tarkistukset eivät löytäneet yksityisiä avaimia, GitHub/OpenAI-tokenmuotoja, merge-markkereita tai epäilyttäviä credential-literaaleja. Tämä on rajattu kuviotarkistus, ei todistus kaikkien mahdollisten salaisuuksien poissaolosta. .env, SQLite, .benchmark-private ja PRIVATE-mallikartat eivät ole seurannassa ja ignore-testit läpäisivät.

**64 historiallista benchmark-tiedostoa on jo Git-seurannassa ja säilyi muuttumattomana.** Niitä ei sekoiteta uusiin väliaikaisiin tiedostoihin eikä poisteta automaattisesti. Rajattu token-/avaintarkistus ei löytänyt niistä salaisuuskuvioita. Fiktiiviset, tarkistetut tulokset voivat olla raportointiaineistoa; yksityinen identiteettikartta, raaka ajonaikainen data ja uusi runtime-evidenssi pysyvät poissa GitHubista.

Omistajan myöhemmin tarkistettavat commit-kokonaisuudet: navigointi/startup/finalisointi + testit/ohjeet; versioidut ammatilliset kehotteet/ohjeelliset tarkistukset/fiktiivinen benchmark; Mistral-diagnostiikka/riippuvuudet/verkkosuojatut testit/raportti. Koodit, testit ja dokumentit ovat katselmointiehdokkaita, eivät automaattisesti hyväksytty julkaisu. Älä julkaise .env:iä, tietokantoja, PRIVATE-karttoja, raakavastauksia, selainprofiileja/lokeja/kuvia tai yksityisiä vertailupaketteja. Omistaja päättää lopullisen commitin sisällön myöhemmin.

## 8. Yksi turvallinen seuraava askel

Aja **vain paikallinen**, verkkoyhteydetön tarkistus siinä PowerShellissä, jossa omat muuttujat on jo asetettu:

```powershell
.\.venv\Scripts\python.exe -m hankeluotsi.mistral_smoke --diagnose
```

Tarkista itse booleaneista epäilty Bearer-etuliite/lainausmerkit/sisäiset välilyönnit sekä käytössä oleva malli ja kuljetuksen trust_env/verify-liput. Avain, ympäristöproxyjen osoitteet ja varmennepolut eivät tulostu. Komento ei varmista avaimen tai tilin oikeuksia, palauta vanhoja virheitä tai tee API-kutsua. Automaattista ympäristömuuttujan korjausta ei tehdä.

**Vain myöhemmän erillisen API-luvan jälkeen:** yksi `--models --diagnostics` tallentaisi samaan tulosteeseen yhden GET:n turvalliset HTTP-/provider-/MIME-/protokollatiedot. Se ei tee generointia tai lisäpyyntöä. Selvitä ensin näytön perusteella, onko kyse JSON-provider-virheestä, ei-JSON-vastauksesta vai riittämättömästä tiedosta. Vertaa konsolin jo olemassa olevia pyyntö-/työtilatietoja paljastamatta avainta. Mahdollinen erillinen POST tai toinen kuljetusvertailu tarvitsee uuden nimenomaisen päätöksen, mallin/hinnan/saldon tarkistuksen ja yhden yrityksen rajan. Tässä työssä lupaa ei käytetty eikä uutta kutsua tehty.

## 9. Suositukset lopulliseen versioon 13.12.2026

1. **Vaikutuslogiikan ihmisarvio ja jäljitettävyys:** tarve→tavoite→toiminta→tuotos→tulos→vaikutus; suhteuta väitteet kestoon, resursseihin, tavoittavuuteen ja seurantaan. Käytä sokkoutettua fiktiivistä rubriikkia ja erottele AI-avusteiset havainnot ihmisen pisteistä.
2. **Mittarien operatiivinen laatu ja lähdefaktat:** lähtötaso, tavoite, yksikkö, tiedonkeruu ja vastuu; puuttuvat tiedot avoimiksi kysymyksiksi. Älä keksi sitoumuksia, osallistujamääriä, rahoituskelpoisuutta tai vahvistettuja kumppaneita.
3. **Arvion kattavuus ja toistettava luotettavuus:** varmista, että kriittinen arvio huomaa epäsuhdan ja puutteellisen vaikutusmekanismin, säilyttää lähdelainaukset ja epävarmuudet. Tee myöhemmin erikseen hyväksytty vaihekohtainen luotettavuuskoe; nykyiset mockit eivät ole10 ensimmäisen yrityksen/stage-mallimittaus tai laatunäyttö.
4. **Julkaisun rajaus ja kuljetusten eksplisiittisyys:** tarkista koko commit-kokonaisuus ja puhdas asennus, pidä pilvi valinnaisena, dokumentoi erikseen SDK:n omat retry-/redirect-oletukset ja tuleva tarkoituksellinen varmennekonteksti tarvittaessa. Uusi muokkaus-/historia-/PDF-toiminto ei kuulunut tähän työhön.
