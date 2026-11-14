# Mistral request diagnosis — 12 November 2026

**Uusi omistajan havainto 14.11.2026:** Large4-yhteys toimii kelvollisen avaimen käyttöönoton jälkeen. Omistajan live-tulos26/32/58 tokenia, katto32, noin1,45s,0 uusintaa ja aiempi `incomplete` eivät ole uusi HTTP400-havainto. Tarkkaa vanhaa palvelinvirhettä ei ole palautettu. [Nykyinen tokenrajan/HTTP-virheen erottelu,256-tokenin testin valmistelu ja offline-varmennus](mistral_connectivity_2026-11-14.md). Tämän dokumentin aiemmat tili-/työtilahypoteesit ovat historiallisia; agentti ei tehnyt uutta API-kutsua.

**Ajantasainen täydennys 13.11.2026:** tuotantosovittimen suodatettu virheenkäsittely on nyt korjattu; tämän dokumentin alkuosa kuvaa aikaisempaa toteutusta. Tarkka korjaus ja uudet testitulokset ovat lopun osiossa "Tuotantosovittimen virheenkäsittely". Aiemman palvelinvirheen tarkkaa sisältöä ei ole palautettu.

## What is established

The reported UI message, “Mistral rejected the request or is unavailable,” originated from a broad non-success HTTP branch. It discarded the status along with the body, so the historical message alone cannot distinguish an invalid request, missing model, account billing issue, permission failure or service outage. No specific historical API/schema/model root cause is asserted.

In this development process, `MISTRAL_API_KEY` is absent and no valid `MISTRAL_MODEL` is configured. Only key-presence and safe model metadata were inspected; no key value was printed or stored. A key in the owner's separate PowerShell does not automatically exist in this process. No account/model-list request, paid generation request or live authentication test was made during this task.

The adapter already uses the documented fixed endpoint `https://api.mistral.ai/v1/chat/completions`, bearer authentication, messages, bounded `max_tokens`, temperature and JSON-schema response mode. Official documentation supports this structure. There is no recorded evidence establishing that the current Pydantic-generated schema is incompatible with the owner's exact model/account, so the implementation does not strip schema constraints, switch formats silently or guess a different model.

## Targeted corrections

`CloudError` now retains only a bounded numeric `http_status`, when available. Fixed error categories distinguish:

| HTTP status | Safe category / next check |
| --- | --- |
| 400 / 422 | Request/schema/parameters need checking; the exact field is unknown without a separately reviewed diagnostic |
| 401 | Authentication failure |
| 402 | Account billing or credits require checking |
| 403 | Workspace/model access or permissions require checking |
| 404 | Requested resource/model identifier/access requires checking |
| 408 / 504 | Timeout reported by the service |
| 413 | Request size requires revision |
| 429 | Rate limit; no automatic retry |
| Other 5xx | Server failure; check service state |
| Other non-2xx, including redirects | Generic HTTP failure; redirect not followed |

These are interpretations of the returned status, not proof of an account's exact balance or a programme requirement. Responses are not parsed or echoed on HTTP failure, and neither headers nor arbitrary exception strings are logged. Existing network/TLS, timeout, malformed-envelope, empty/invalid JSON, schema and incomplete-output handling remains. Unexpected errors are still sanitized. The actual API key remains environment-only and server-echoed key text is redacted on successful transport.

`MistralClient.generate` additionally accepts explicit `max_tokens` and `timeout_seconds` for draft/review calls. Defaults remain **512 / 120 seconds** for the existing concept flow. Allowed bounds are integer 128–8192 output tokens and 1–600 timeout seconds; booleans and out-of-range values are rejected before a request. Output JSON also rejects `NaN`/`Infinity`, which are not JSON numeric values, before Pydantic validation. No repair request or automatic provider fallback was introduced.

## Offline evidence

The focused mock suite covers the fixed endpoint/request/schema, environment isolation, key/consent absence, both direct and factory consent enforcement, all new HTTP categories, sanitized secret-bearing exceptions, ignored provider usage details, malformed JSON/envelopes, nonstandard numeric constants, schema errors, truncation/unknown finish, size limits, budget bounds and explicit draft budgets. Benchmark/report/blind-review compatibility is retained; human scores remain null and tests do not contact providers. Final commands/results are recorded in the main development log.

## Exact remaining verification

1. Launch Streamlit or the benchmark from the **same PowerShell process** where both environment variables are configured. Run the existing no-generation preflight first; do not print the key or environment dump.
2. After owner approval of read-only account access, verify the exact configured model against the account's model inventory. A valid-looking identifier does not establish access or schema support.
3. Verify current pricing, account balance, privacy terms and a bounded input/output cost ceiling before approving one fictional cloud smoke test. None is established by the environment-presence check.
4. Inspect the new safe error category and numeric status if that approved smoke fails. A 400/422 points to request/schema/model-specific constraints, but does not identify the offending field by itself. Do not remove validation blindly or paste raw provider bodies containing project text/credentials into public logs.
5. Confirm a normal finish reason, strict Pydantic validity, expected output language and preserved local state. Check actual token usage/billing separately. Timeout or client failure does not prove that server processing/billing did not occur.

No successful live Mistral repair, account access, model availability or paid benchmark result is claimed. No credential loader, cloud default, retry loop, model substitution, dependency or unrelated feature was added.

Official references checked for this diagnosis: [Chat Completion API](https://docs.mistral.ai/api), [custom structured outputs](https://docs.mistral.ai/inference/conversations/structured-output/custom). Existing secure shell instructions remain in [mistral_setup.md](mistral_setup.md).

## Follow-up — offline readiness, 13 November 2026

See the current Finnish [readiness report and exact single-smoke instructions](mistral_readiness.md). The historical HTTP cause is still unknown; the old generic branch lacked status. Current agent-process environment has neither Mistral variable, and the new no-network preflight returns missing_key. That is a current launch-environment blocker, not proof that a previously received HTTP rejection was caused by an absent key. The owner's configured PowerShell is a separate environment and was not read or copied.

Installed OpenAI3.6.0 is the local SDK; no Mistral SDK is installed. Existing direct httpx2 transport retained. Official chat/reasoning docs confirm string or typed content chunks: final text chunks are now supported, thinking chunks excluded from the answer, and unsupported tools/media rejected. Null final content retains truncation classification instead of concealing it as a generic envelope error. Unknown finish remains failure for cloud saves. Strict one-attempt type, echoed-key redaction and refusal to treat key text as model metadata are offline-tested. HTTP429 wording now acknowledges rate or quota limits without claiming a known billing cause. Fixed HTTP401/402/403/404/400/422/408/413/429/504/5xx categories remain; no raw HTTP error body is logged or displayed.

Reported model and token usage now leave the adapter as optional non-sensitive result metadata. A new standalone smoke command defaults to zero-network configuration checking; explicit owner execution permits one512-token fictional ConceptPaper request, no retry/extra account request/database. Fresh private request/receipt artifacts include source hashes and safe error categories. Usage/pricing estimates remain distinct from unknown actual billing. No model identifier, endpoint, schema constraint or default provider was silently changed. No live Mistral success or model-quality advantage is claimed.

## Tuotantosovittimen virheenkäsittely — 13.11.2026

**Vahvistetut puutteet:** MistralTransport käytti vain `_http_error(status)`-kutsua. Smoke-moduulin aikaisempi turvallinen parseri ei siten korjannut varsinaista sovitinta: palvelimen message/param/code hävisivät. Lisäksi suoraan importattu httpx2 puuttui requirements.txt:stä. Paikallisen OpenAI SDK -reitin toimivuus ei vahvista erillisen Mistral-reitin toimintaa. Aiemmat kaksi HTTP400-havaintoa ovat omistajan ilmoittamia; vanhoja virherunkoja ei ole saatu eikä keksitty.

**Täsmälliset muutokset:**

- `mistral_client.py`: yhteinen `request_error_diagnostic` ja suodatinapufunktiot siirrettiin smoke-moduulista varsinaiseen sovittimeen. `_http_error(status, response=..., secret=...)` lukee virhevastauksen ennen `CloudError`-nostoa kaikissa HTTP-virheissä. Poikkeus säilyttää `http_status`, `provider_error_code`, `parameter`, `sanitized_message` ja suodatetun `diagnostic`-olion. `str(error)` ja `args` pysyvät samoina turvallisina käyttöliittymäviesteinä; vastaus-/pyyntöoliota, otsakkeita tai raakaviestiä ei liitetä poikkeukseen.
- Virhe-JSONin parsintaraja on **64 KiB**, suodatetun viestin enimmäispituus **240 merkkiä**. Rikkinäinen JSON, HTML, muu JSON-juurityyppi, liian suuri runko tai parserin poikkeus säilyttää alkuperäisen HTTP-luokan/statuskoodin. Kokoraja koskee diagnostiikan parsintaa jo puskuroidusta HTTP-vastauksesta, ei verkkolatauksen muistirajaa.
- Vain sallitut koodinimet/lyhyet numerokoodit ja tunnetut parametrinimet säilytetään. Viesti muodostetaan tunnistetusta virhelauseesta ja vapaat arvot peitetään; tuntematon viesti jää peitetyksi. Pyynnössä oikeasti käytetty avain peitetään **ennen** viestin katkaisua, myös jos ympäristömuuttuja vaihtuu kutsun aikana. Suodatettu viesti ei ole sanatarkka alkuperäinen vastaus.
- Mistralin HTTPTransport käyttää nimenomaisesti `retries=0`; ei uudelleenohjauksia, automaattista korjauspyyntöä tai mallivaihtoa. Smoke ja ConceptPaper-smoke säilyttävät samat turvalliset diagnostiikat. `--diagnose` tulostaa vain mallin, kenttänimet, tokenrajan ja viestien määrän/roolit: ei viestisisältöjä tai kokonaista pyyntörunkoa.
- `requirements.txt`: lisätty todennetut nykyiset suorat riippuvuudet **httpx2==2.16.0** ja **certifi==2026.10.23**. Jälkimmäinen on jo käytössä funding_eu-moduulin TLS-kontekstissa. OpenAI3.6.0:n asennettu vaatimus httpx2>=2.7.0,<3 hyväksyy valitun version. Paketteja ei asennettu eikä OpenAI SDK -reittiä vaihdettu. Offline-importtiauditointi kattaa kaikki sovelluksen suorat kolmannen osapuolen importit; `pip check` ei löytänyt ristiriitoja. Tämä ei ole puhtaan ympäristön asennustesti.

**Verrattu viralliseen sopimukseen:** [Chat Completions](https://docs.mistral.ai/api/endpoint/chat) määrittelee nykyisen POST-osoitteen, model/messages/max_tokens/stream-kentät sekä valinnaiset temperature- ja json_schema-vastemuodon. Tuotannon nykyinen rakenne säilyi: kaksi system/user-viestiä, temperature0.2, vaihekohtainen tokenraja ja Pydantic-JSON-skeema. Lyhyt yhteysprobe käyttää edelleen yhtä fiktiivistä viestiä ja32 tokenia. [Virhesopimus](https://docs.mistral.ai/resources/error-glossary) määrittelee message/type/param/code-kentät, joita yhteinen parseri nyt käsittelee. Virallisen SDK:n retry-suositusta ei otettu käyttöön, koska omistaja edellyttää yhtä yritystä.

**Testit:** kohdennettu ajo **160 passed / 7.62s**; koko offline-sarja **789 passed, 2 skipped / 58.08s**, live-rahoitushaku pois ja oletustietokanta uutena väliaikaisena SQLite-tiedostona. Ohitukset ovat erikseen sallittavia verkkotestejä. Mockatut tuotantosovittimen HTTP400-testit sisältävät message/param/code-kentät, litteän ja sisäkkäisen virheen, epäkelvot/isot vastaukset sekä salaisuudet poikkeuksen attribuuteissa, args-/str-/repr-muodoissa ja lokeissa. Regressiot kattavat myös avaimen vaihtumisen, katkaisurajan ylittävän avaimen, nykyiset request-parametrit, yhden POST-kutsun ja FI/EN-työnkulun säilymisen. Koko sarjassa ei tehty live-API-kutsuja. Git-diff- ja säilytystarkistukset kirjataan kehityslokiin.

**Epävarmuus:** tämä korjaa vahvistetun tiedonmenetyksen ja riippuvuusmäärittelyn. Se ei osoita, että historiallinen400 johtui mallinimestä, käyttöoikeudesta, skeemasta tai tokenrajasta. `actual_billed_cost=null` on tuntematon veloitus. Aiemmat palvelinvirheet voivat olla peruuttamattomasti kadonneet; uusia kutsuja ei tehty niiden selvittämiseksi. Tallennetut projektit, SQLite, tuotantokehotteet/skeemat ja aiempi koeaineisto säilytetään.

## Vanha ja uusi avain: sama mallilista-400 — 14.11.2026

Omistaja ilmoitti malliluettelon haun palauttavan myös uudella avaimella HTTP400:n ja molempien mallikenttien null-arvot. Tämä on omistajan raportoimaa uutta havaintoa, ei agentin tekemä API-koe. Todellista uutta avainta, sen työtilaa tai käytettyä PowerShell-ympäristöarvoa ei ole tarkistettu.

**Offline-todennetut asiat:** nykyinen GET käyttää kiinteää `/v1/models`-osoitetta, ei lähetä runkoa/queryä/malliasetusta, ja muodostaa yhden Bearer-otsakkeen kutsuhetken ympäristöavaimesta. Avainta ei cacheta kutsujen välillä. Puuttuva Content-Type ei ole virhe: [virallinen Models-esimerkki](https://docs.mistral.ai/api/endpoint/models) käyttää GET:iä ja Authorizationia ilman pyyntörunkoa. Retry, redirect ja ympäristöproxy on pois; Client- ja HTTPTransport-tason trust_env=False ja TLS-varmennus päällä. Muistissa ajettu oikea HTTPTransport/httpcore2/H11 vahvistaa myös HTTP/1.1-rivin, Hostin ja tyhjän rungon. Uutta pyyntörakenne- tai kirjastovikaa ei löytynyt; tuotantokoodia ei muutettu arvauksella.

HTTP400 säilytetään suoraan saadun HTTP-vastauksen statuksesta. Yhteys-/TLS-poikkeusta tai mallilistan JSON-parsintavirhettä ei muuteta paikallisesti400:ksi. Non2xx-polussa null-kentät tarkoittavat **tuntematonta luetteloa**, eivät mallin puuttumista. Normaali kolmen kentän tuloste ei yksin kerro palvelimen tarkempaa hylkäyssyytä. Aiemmat viestit eivät palaudu tästä havainnosta.

**Yhteinen tilikonteksti on mahdollinen mutta vahvistamaton:** [avaindokumentaation](https://docs.mistral.ai/admin/identity-access/api-keys) mukaan avain kuuluu luontityötilaansa ja käyttää sen resursseja/rajoja. Uusi avain ei luo uutta organisaation laskutus-/API-kontekstia. Dokumentaatio erottaa standardin API-käytön Studio-avaimen Vibe- ja vanhoista Mistral Code -avaimista. Kaksi samassa kontekstissa luotua avainta voi siis jakaa saman rajoituksen. Se ei todista, että omistajan oikeudet puuttuvat tai että laskutuksessa on vika. Sama verkkoreitti, samanlaiset avaimen asetustavat ja palvelun reunakäsittely ovat yhä mahdollisia yhteisiä tekijöitä. Todellinen palvelinvirhe puuttuu, joten niitä ei voi erottaa varmuudella.

**Testit:** lisätty kaksi regressiota: kaksi eri fiktiivistä avainta erillisissä peräkkäisissä400-kutsuissa käyttää kumpikin uutta ympäristöarvoa, yksi GET per komento; virheellinen generointimallin asetus ei vaikuta onnistuvaan GET-mallilistaukseen. Kohdennettu offline-ajo **235 passed in3.33s**, sisältäen Mistral-smoken/sovittimen, HTTP1-kooderin/TLS-asetukset ja verkkosuojan. Kaikki HTTP-vastaukset mockattiin tai tuotettiin muistissa. Ei oikeita API-kutsuja, uusia paketteja tai koko testisarjan toistoa muuttumattomalle tuotantokoodille.

**Yksi suositeltu seuraava toimi:** tarkista Mistral-konsolin jo olemassa olevasta API Keys -metadatasta uuden ja vanhan avaimen **Type, Workspace, active/expiry ja Last used** sekä vastaavan organisaation API-/käyttöpakettikonteksti. Älä näytä tai lähetä avainten arvoja äläkä tee uutta testi-API-kutsua. Last used voi päivittyä viiveellä ja on vain tukeva havainto siitä, käytettiinkö uutta avainta. Tämä rajaa yhteisen työtilan/avaintyypin mahdollisuutta ilman uutta generointi- tai mallilistapyyntöä.
