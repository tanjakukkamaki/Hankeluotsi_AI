# Mistral-yhteys ja tokenrajan diagnostiikka — 14.11.2026

## Uusi havainto ja sen rajat

Omistaja ilmoitti Mistral Large 4 -yhteyden toimivan kelvollisen API-avaimen käyttöönoton jälkeen. Viimeisimmän omistajan tekemän live-testin tiedot:

| Tieto | Omistajan ilmoittama arvo |
| --- | --- |
| Prompt / completion / total tokens | 26 / 32 / 58 |
| Enimmäisulostulo | 32 tokenia |
| Automaattiset uusinnat | 0 |
| Vanhan smoke-tulosteen virheluokka | `incomplete` |
| Aika | noin 1,45 s |

Nämä eivät ole tämän työsession aikana agentin mittaamia tuloksia. Tarkkaa HTTP-statusta, `finish_reason`-arvoa, vastaustekstiä tai aiempien HTTP400-virheiden palvelinrunkoja ei toimitettu. Niitä ei rekonstruoida. Omistajan ilmoitus ratkaisee aiemman tunnistautumisesteen; vanhat työtila-, laskutus- ja mallihypoteesit eivät ole osoitettuja syitä. 32/32-tokenkäyttö viittaa ulostulobudjetin loppumiseen, mutta ilman valmistumissyytä yksin tokenmäärä ei todista katkeamista. Aiempi `incomplete` ei itsessään tarkoita HTTP400-virhettä.

## Täsmälliset muutokset

`hankeluotsi.mistral_smoke` erottaa nyt HTTP-pyynnön hyväksymisen, lopullisen vastauksen valmistumisen ja tokenrajaan katkeamisen:

| Havainto | Uusi tuloste |
| --- | --- |
| HTTP2xx | `api_request_succeeded=true`; valmistuminen tarkistetaan erikseen |
| Ei-2xx | `outcome=http_api_error`, säilytetty status ja yhteinen suodatettu provider-diagnostiikka |
| `finish_reason=length` | `outcome=output_token_limit`, sama `error_code`, `completion_truncated=true`; selitys kertoo, että API-pyyntö onnistui |
| `finish_reason=model_length` | `outcome=context_limit`, `completion_truncated=true` |
| Ei-tyhjä lopullinen teksti ja `stop` | `success=true`, `outcome=complete`, vaikka tokenkäyttö osuisi kattoon |
| Puuttuva/tuntematon valmistumissyy | `incomplete_response`, `error_code=incomplete`; katkeamista ei arvata |
| Rikkinäinen/tyhjä valmis vastaus, verkkovirhe tai aikakatkaisu | Erillinen response-/connection-/timeout-tulos |

`output_token_limit_reached` näyttää erikseen raportoidun completion-tokenmäärän suhteen kattoon; `length` vahvistaa rajan saavuttamisen myös ilman käyttömetatietoa. HTTP2xx ei yksin takaa kelvollista vastausrakennetta tai täydellistä vastausta. Avainta, otsakkeita, vastaustekstiä tai raakavirheitä ei tulosteta. Toteutunut laskutus jää tuntemattomaksi, ellei palvelin sitä raportoi; tokenkäyttö ei ole veloitustosite.

Minimaalinen fiktiivinen Meadow/“Reply only OK” -kehote säilyy, eikä siinä ole JSON-skeemaa, reasoning- tai temperature-parametria. Oletuskatto on nyt **256 tokenia**. Eksplisiittiset sallitut katot ovat 32, 128, 256 ja 512; vanha 32-tokenin testi on edelleen toistettavissa. Väärä raja hylätään ennen HTTP-asiakasta. Yksi POST, **0 uusintaa**, ei automaattista budjetin nostoa tai mallinvaihtoa. 256 antaa lyhyelle vastaukselle enemmän tilaa, mutta valmistumista ei luvata ilman uutta erikseen hyväksyttyä testiä.

## Streamlitin asetusten varmennus

Lähdekoodi ja FI/EN-AppTest mockatulla varsinaisella Mistral-asiakkaalla varmistavat, että käyttöliittymän Mistral-polut käyttävät samaa kiinteää Chat Completions -endpointia, `MISTRAL_API_KEY`- ja `MISTRAL_MODEL`-ympäristölähdettä, yhtä Bearer-tunnistautumista, varmennettua TLS:ää sekä client- ja transport-tason `trust_env=False`-asetusta. Ei uudelleenohjauksia tai automaattisia uusintoja. FI/EN-työnkulkutesti tarkistaa mallin `mistral-large-4` ja fiktiivisen testiavaimen todellisesta muodostetusta mock-pyynnöstä.

Tuotantobudjetteja ei muutettu: concept 512/120 s, draft 4096/180 s, review 2048/180 s. Tuotanto lähettää vaiheen skeeman; minimaalinen yhteystesti ei. Lyhyt toimiva yhteys ei siis todista näiden skeemojen hyväksyntää, validia ConceptPaperia tai suunnittelun laatua. Jo käynnissä oleva Streamlit-prosessi ei saa PowerShelliin myöhemmin asetettua avainta automaattisesti. Sen nykyisen avaimen kelpoisuutta ei luettu tai live-varmennettu.

## Offline-varmennus ja seuraava askel

Komento (live funding pois käytöstä, bytecode pois; testien verkkosuoja ja fiktiiviset mockit):

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/test_mistral_smoke.py tests/test_mistral.py tests/test_mistral_transport_safety.py tests/test_mistral_workflow.py
```

**256 passed in 10.33 s.** Mukana omistajan 26/32/58-tietoja vastaava synteettinen `length`-tapaus, kaikki sallitut/virheelliset katot, HTTP400:n ja tokenrajan erottelu, stop katolla, tuntematon valmistumissyy, tietoturvaregressiot sekä FI/EN-Streamlitin suostumus–generointi–arviointi–hyväksyntä–vientipolut. Myös HTTPTransport/httpcore2/H11-koodaus testataan muistissa, ei ulkoisella yhteydellä. Koko testisarjaa ei ajettu tässä rajatussa tehtävässä; aikaisempi koko sarjan 871 passed / 2 skipped on historiallinen tulos. `git diff --check` ja `git diff --cached --check` läpäisevät.

Turvallisin välitön askel on tallentaa keskeneräinen lomake tarvittaessa ja käynnistää Streamlit uudelleen **samasta toimivan avaimen ja mallin sisältävästä PowerShellistä**, sitten tarkistaa Mistralin asetustila ilman generointia. Älä tulosta ympäristömuuttujia tai avainta. Tämän jälkeen omistaja voi erikseen hyväksyä yhden seuraavan testin. Valmisteltu komento, jota agentti ei ajanut:

```powershell
.\.venv\Scripts\python.exe -m hankeluotsi.mistral_smoke --live --max-output-tokens 256
```

Uutta maksullista pyyntöä ei ole nyt hyväksytty tai tehty. Ei mallilistakutsua, benchmarkia, tallennettujen projektien muutosta, commitia tai pushia. Alkuperäiset benchmark-tulokset ja kaikki aiemmat työt säilyvät; odotetaan omistajan arviota.
