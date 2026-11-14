# Mistralin valmius ja suunnittelulaadun vertailu — 13.11.2026

**Nykytila 14.11.2026:** omistaja ilmoittaa Large4-yhteyden toimivan kelvollisella API-avaimella: käyttö26/32/58 tokenia, katto32,0 uusintaa, noin1,45s ja vanha `incomplete`-luokka. Tämän session agentti ei tehnyt API-kutsuja. Smoke erottaa nyt HTTP/API-virheen ja tokenrajaan katkeamisen; lyhyen testin uusi oletuskatto on256, vanha32 on valittavissa. [Täsmälliset muutokset,256 offline-testin tulos, Streamlitin asetusten rajat ja valmisteltu komento](mistral_connectivity_2026-11-14.md). Alla olevat400- ja tilihypoteesit kuvaavat historiallista selvitystä, eivät nykyistä todettua estettä. Älä toista live-/mallilistapyyntöjä ilman uutta erillistä lupaa.

**Historiallinen offline-yöntarkistus 13.11.:** omistaja ilmoitti kolme generoinnin400-virhettä ja myös mallilista-GET:n400-virheen. Uusia API-kutsuja ei tehty. [Koko tutkimus, testit ja Git-rajaukset](overnight_engineering_2026-11-13.md) erottavat todennetut ohjelmistopuutteet tuolloin tuntemattomasta palvelinjuurisyystä. Alla olevia live-/mallilistakomentoja ei pidä toistaa ilman erillistä uutta lupaa.

**Historiallinen tila 13.11.:** integraatio on offline-testattu ja yksi erikseen hyväksyttävä Mistral-smoke on valmisteltu. Tuolloin oikeaa Mistral-generointia, mallin käyttöoikeutta, saldoa tai laskutusta ei ollut vahvistettu. Tuossa työssä tehtiin **0 malligenerointia ja 0 Mistral-tili/API-kutsua**. Testien mock-vastaukset eivät ole mallien suorituskykytuloksia. Qwen pysyy oletuksena, eikä käyttöliittymän avaaminen, navigointi tai tavallinen pytest tee ulkoisia mallikutsuja.

## Aiemman virheen diagnoosi

Vanha yleisviesti `Mistral rejected the request or is unavailable...` kadotti HTTP-statuksen. Sen perusteella ei voi erottaa tunnistautumista, mallioikeutta, laskutusta, skeemaa tai palvelukatkoa. Nykyisen sovittimen kautta kokonaan puuttuva avain estää pyynnön jo ennen HTTP:tä, joten avaimen puuttumista ei esitetä todistettuna selityksenä tuolle historialliselle HTTP-virheelle.

Todennettu nykyinen este on, ettei tämän agenttiprosessin ympäristössä ole kumpaakaan Mistral-muuttujaa. Avaimesi voi silti olla omassa PowerShellissäsi. Siksi käynnistysympäristön periytyminen on ensimmäinen käytännön tarkistus. Toisen prosessin muistista tai ympäristöstä ei etsitty eikä kopioitu salaisuutta. Uusi verkkoyhteydetön esitarkistus palautti `configured=false`, `error_code=missing_key`, `network_calls=0`; se ei tarkistanut omaa PowerShell-ikkunaasi.

Asennettuna on OpenAI SDK3.6.0 paikallista yhteensopivaa asiakasta varten; `mistralai`-SDK:ta ei ole. Mistral käyttää nykyistä suoraa `httpx2`-sovitinta. SDK-vaihtoa tai uutta riippuvuutta ei tarvita. Kiinteä nykyinen chat-endpoint, tunnistautumistapa ja JSON-schema-pyyntö säilyivät; mallin tunnistetta ei arvata eikä vaihdeta.

HTTP401 erotetaan tunnistautumiseksi,402 laskutus-/krediittiasiaksi,403 oikeudeksi,404 resurssi-/malliasiaksi,400/422 pyyntö-/skeema-asiaksi,429 nopeus- tai käyttörajatarkistukseksi,408/504 aikakatkaisuksi ja muut5xx palveluvirheiksi. Luokat eivät todista tilin tarkkaa ongelmaa. Raakavastauksia, otsakkeita tai poikkeusten salaisia sisältöjä ei näytetä.

Vastausparsinta hyväksyy nyt dokumentoidut tekstipalalistat tavallisen merkkijonon lisäksi ja poimii vain lopulliset tekstiosat. Ajatteluosia ei tallenneta vastaukseksi. Tyhjää tai tokenrajaan päättynyttä vastausta ei hyväksytä, eikä tuntematonta valmistumissyytä nimetä `stop`-tilaksi. Raportoitu malli ja tokenkäyttö säilyvät tulosmetatietoina. Avaintekstin virheellinen käyttö mallimuuttujassa estetään ennen pyyntöä/metatiedon tallentamista.

Perustelut: [Mistralin chat-kuvaus](https://docs.mistral.ai/inference/conversations/chat-completion), [ajattelu- ja tekstiosat](https://docs.mistral.ai/inference/conversations/reasoning), [chat-pyynnön rakenne](https://docs.mistral.ai/api/endpoint/chat). Tilin ja valitun mallin todellinen hyväksyntä on edelleen live-testin asia.

## Kehotteet ja yhteensopivuus

| Vaihe | Uusi varsinainen kehote | Säilynyt sopimus ja oletusbudjetti |
| --- | --- | --- |
| Konsepti | `concept_v2` | ConceptPaper, yksi tiivis O/A/R/I-ketju,512 ulostulotokenia; paikallisen asiakkaan asetukset ennallaan, Mistralin HTTP-vaiheaikakatkaisu120s |
| Hakemusluonnos | `draft_workflow_v2` | ApplicationDraft v1,4096 tokenia/180s; paikallinen native reasoning off, valinnainen Mistral |
| Arvio | `review_workflow_v3` | Sisäinen ReviewSelection → tarkat lähdelainaukset → alkuperäinen ReviewReport v1,2048 tokenia/180s |

Mistralin draft/review-kutsujen yleinen ulkokehote on edelleen `draft_v1`/`review_v1`; varsinainen ammatillinen sisältö on yllä olevassa workflow-versiossa. Vertailusuunnitelma kirjaa molemmat versiot. Qwenin oletustunniste on edelleen `qwen3.5-4b`, mutta tässä offline-työssä ei varmennettu uudelleen ladattua tiedostoa, kvantisointia tai runtimea. Mistralin täsmällinen malli tulee vain omasta `MISTRAL_MODEL`-muuttujastasi.

Uudet kehotteet pyytävät tarpeen, tavoitteiden, työpakettien, toiminnan, tuotosten, tulosten, mittareiden ja vaikutusmekanismin yhteyttä sekä resursseihin ja seurantaan suhteutettua laajuutta. Arvioija ohjataan vertaamaan alueellisia vaikutusväitteitä toiminnan kestoon ja tavoittavuuteen ennen kosmeettisia huomioita. Yksi työpaketti voi riittää rajattuun pilottiin; kahden päivän työpaja ei yksin todista laajaa aluekehitysvaikutusta. Lukumääriä, budjetteja, sitoumuksia, varmoja kumppaneita tai kelpoisuutta ei saa keksiä. Puuttuvat asiat jäävät kysymyksiksi.

Uudet deterministiset **ohjeelliset** huomiot tunnistavat toistuvia/otsikoituja kumppaninimiä sekä selvästi menneitä tai virheellisiä aikataulupäiviä annetun vertailupäivän suhteen. Ne eivät päättele suunnitelman ammatillista riittävyyttä tai rahoitusehtoja, eivät muokkaa tekstiä eivätkä muuta tallennettuja hyväksyntätarkistuksia. Historiallinen päivämäärä ja saman organisaation eri roolit voivat olla tarkoituksellisia. Nykyinen UI näyttää huomiot omassa avattavassa osiossa. Vanhojen hyväksyttyjen tietueiden vienti säilyy; repositoryä, skeemoja, hyväksynnän lukitusta ja nelivaiheista käyttöliittymää ei muutettu.

Kehotteiden selkeyttä parannettiin, mutta parempaa mallisisällön laatua ei väitetä ennen aitoja vastauksia ja omistajan arviota. Historiallinen A/B/C-kehotekokoelma ja sen baseline-teksti säilyivät; uusi tuotantoversio ei korvaa vanhoja koetuloksia.

## Pieni toistettava vertailuprotokolla

`planning_benchmark` on **offline-työkalu**: se jäädyttää pyynnöt, tarkistaa ja tuo myöhemmin kerättyjä vastauksia sekä valmistaa A/B-arviointiaineiston. Se ei ole automaattinen maksullinen monimalliajaja. Vastauksia kerätään vasta erillisellä hyväksynnällä täsmälleen suunnitelman syötteistä ja tallennetaan niiden pyynnöt/vastaukset yksityisesti.

| Tapaus | Kieli | Jäädytetty arviointisyöte |
| --- | --- | --- |
| P01 | EN | Kuvitteellisten taiteilijoiden yritysosaamispilotti: konsepti, luonnos ja arvio |
| P02 | FI | Kuvitteellisten pienyritysten synteettinen tekoälykokeilu: konsepti, luonnos ja arvio |
| P03 | EN | Tarkoituksella heikko luonnos: alueellinen vaikutusväite, yksi työpaketti, kahden päivän työpaja,2024-aikataulu ja toistuvat kumppanimerkinnät; arvio |
| P04 | FI | Vastaava tarkoituksella heikko arviointiluonnos suomeksi |

Tämä on8 pyyntöä mallia kohti, yhteensä16 mahdollisessa myöhemmässä parivertailussa. Seedatut konseptit/luonnokset ovat käsin kirjoitettuja fiktiivisiä kontrollisyötteitä, eivät kummankaan mallin tuotoksia. Vaiheita verrataan samoilla lähtösyötteillä erikseen; kyseessä ei ole generoitujen vaiheiden läpi kulkeva kokonaisprosessin koe. Kahdeksan pyynnön pilotti ei täytä AGENTS:n10 ensimmäisen yrityksen vaihekohtaista luotettavuusporttia eikä riitä julistamaan voittajaa.

Suunnitelma tallentaa skeemat, kehotteet, vertailupäivän, asetukset, lähdehashit, versiot ja8 pyyntöhashia. Uusi oma suunnitelma valmistellaan ilman verkkoa:

```powershell
.\.venv\Scripts\python.exe -m hankeluotsi.planning_benchmark plan `
  --reference-date 2026-11-13 --output .benchmark-private/planning-owner-01/plan
```

Tuloksettomat rivit ovat `not_run`. Niitä ei hyväksytä tuloksiksi. Myöhempi tuonti vaatii jokaisen suunnitellun yrityksen täsmälleen kerran, myös epäonnistumiset, sekä erillisen `recorded_live`/`offline_mock`-merkinnän. Merkintä kuvaa aineiston toimittajan ilmoitusta; työkalu ei itsenäisesti todista API-kutsun tapahtumista. Lähteen muuttuminen vaatii uuden suunnitelman tai tallennetun revision. Vanhoja hakemistoja ei ylikirjoiteta.

```powershell
.\.venv\Scripts\python.exe -m hankeluotsi.planning_benchmark import `
  --plan .benchmark-private/planning-owner-01/plan/plan.json `
  --responses .benchmark-private/planning-owner-01/qwen-responses.json `
  --output .benchmark-private/planning-owner-01/qwen-import
```

Tee sama erikseen Mistral-vastauksille. Syötemuoto on valmistetussa `responses-template.json`-tiedostossa; älä täytä puuttuvia havaintoja arvauksilla. Vain oikeasti raportoidut latenssit, käyttömäärät ja mallimetatiedot tallennetaan. Validointi ei mittaa tuodun tiedoston käsittelyaikaa mallin generointiajaksi. Tuntematon finish säilyy tuntemattomana, vaikka JSON/Pydantic menisi läpi. Paikallisen native-reitin skeematoimitus ja reasoning off sekä pilven JSON-schema-moodi ovat teknisiä eroja, jotka on kirjattava todellisiin keräysmetatietoihin.

```powershell
.\.venv\Scripts\python.exe -m hankeluotsi.planning_benchmark blind `
  --reports .benchmark-private/planning-owner-01/qwen-import/results.json .benchmark-private/planning-owner-01/mistral-import/results.json `
  --output .benchmark-private/planning-owner-01/blind
```

A/B-paketissa ei ole tarjoaja-, malli-, aika- tai tokenmetatietoja. `PRIVATE-model-map.json` pysyy erillään. Tunnettujen mallinimien esiintyminen tulostekstissä estää paketin valmistamisen; omistajan on silti tarkistettava epäsuorat tunnistamisvihjeet. Ihmisarvio ja AI-avusteinen arvio saavat eri tyhjät lomakkeet. Rakenteellinen täydellisyys tarkoittaa vain skeeman vaatimien kenttien läsnäoloa; ammatillinen täydellisyys, suhteellisuus, vaikutuslogiikka, kieli ja kriittisyys jäävät arvioitaviksi.

Kulut lasketaan vain soveltuvan, omistajan varmistaman Pricing-tiedon, täsmäävän raportoidun mallin, tokenkäytön ja laskentaperusteen avulla. Muulloin arvio on null. Lähde, valuutta, hinnat ja tarkistuspäivä säilytetään raportissa; laskutettua toteutunutta kulua ei keksitä. Kaikki ajonaikainen aineisto ja mallikartat pysyvät ohitetussa `.benchmark-private`-hakemistossa. Julkaistavaksi sopivat tarkistetut lähdekoodi, synteettiset fixturet ja menetelmäkuvaus.

## Yhden Mistral-smoken täsmälliset vaiheet

### Mallipääsyn manuaalinen tarkistus: `--models`

**Historiallinen manuaaliohje, nyt vain myöhemmän erillisen API-luvan jälkeen.** Agentti ei suorita tätä eikä uutta GET:iä tarvita nykyiseen offline-tutkimukseen. Käytä silloin projektikansiota ja samaa PowerShelliä, jossa `MISTRAL_API_KEY` on jo asetettuna:

```powershell
.\.venv\Scripts\python.exe -m hankeluotsi.mistral_smoke --models
```

Tämä on omistajan käsin käynnistettävä, erillinen **yksi GET** osoitteeseen `https://api.mistral.ai/v1/models`. Se ei generoi tekstiä, lähetä projektitietoja tai tarvitse `MISTRAL_MODEL`-asetusta. Ei POST-, lämmittely-, uusinta-, uudelleenohjaus-, proxy- tai muita API-pyyntöjä. Käytössä on30 sekunnin HTTP-vaiheaikakatkaisu ja `HTTPTransport(retries=0)`. Agentti ei suorittanut tätä komentoa tai mitään muutakaan live-pyyntöä.

Tuloste sisältää vain kolme kenttää:

- `http_status`: palvelimen HTTP-status tai null, jos vastausta ei saatu/avain puuttuu.
- `mistral_large_model_ids`: järjestetty, duplikaatiton lista julkisen Mistral Large -tunnisteen muotoisista palautetuista tunnisteista. Muiden mallien tunnisteita, ft-/custom-nimiä, kuvauksia, omistajatietoja tai raakavastausta ei näytetä. Suodatin hyväksyy rajatut latest-/numeeriset versiot ja niiden latest-/preview-päätteet; mielivaltaisia uusia nimimuotoja ei julkaista.
- `mistral_large_4_listed`: true vain täsmälliselle `mistral-large-4`-tunnisteelle. Alias `mistral-large-latest` tai versio `mistral-large-4-0` ei yksin muuta tätä trueksi. false tarkoittaa, ettei täsmällinen tunniste ole kelvollisessa saadussa listassa; se ei ole kaikkien aliasten tai tilin käyttöoikeuksien lopullinen tuomio.

HTTP-virhe, puuttuva avain, verkkovirhe tai epäkelpo vastaus jättää listan ja löytymistiedon **null**-arvoiksi, ei tyhjäksi listaksi/falseksi. Virherunkoja, avainta, autentikointiotsaketta tai poikkeustekstiä ei tulosteta. JSON-parsintaa ei tehdä yli1 MB:n puskuroidulle vastaukselle; enintään10000 mallikorttia/256 näytettävää Large-tunnistetta. Tämä on parsintaraja, ei verkkolatauksen muistiraja. Paluukoodi0 tarkoittaa kelvollista listaa (myös tyhjää),1 HTTP-/sisältövirhettä ja2 puuttuvaa avainta/puuttuvaa HTTP-vastausta tai virheellisiä valintoja. `--models` ei yhdisty muihin ajotiloihin.

[Virallinen Models API](https://docs.mistral.ai/api/endpoint/models) määrittelee Bearer-tunnistautumisen ja käyttäjälle saatavien mallien `data`-listan. Dokumentaation esimerkissä on myös suora taulukko; molemmat muodot tuetaan. Näkyminen listassa ei vielä varmista generointipyynnön parametreja, skeematukea tai laskutusta. [Chat-määrittely](https://docs.mistral.ai/api/endpoint/chat) sallii kokonaisluku-`max_tokens`-kentän ja boolean-`stream`-kentän (oletusfalse); input+ulostulokatto ei saa ylittää kontekstia.32 tokenia ei ole dokumentoitu yleisesti kielletyksi. Minimaalinen smoke pysyy skeemattomana, yhdellä user-viestillä,32 tokenilla ja stream=false-valinnalla. Sen parametreja ei muutettu eikä aiempien HTTP400-virheiden syytä keksitty.

Offline-varmennus: **194 passed in3.01s**, kohdennetut smoke-/tuotantosovitintestit. Mallilistatestit kattavat yhden GET:n ilman generointia, molemmat dokumentoidut vastausmuodot, exact-ID/alias-erottelun, salaisuuksien ja yksityisten mallikenttien peittymisen, puuttuvat asetukset, HTTP-/timeout-/rikkinäiset/isot vastaukset ja ristiriitaiset CLI-valinnat. Oikean avaimen mallilistaa ei ole haettu agentin toimesta.

**Yöntarkistuksen lisäys:** suppea `--models` säilyttää kolme kenttäänsä. Valinnainen `--models --diagnostics` lisää saman GET:n turvallisen provider-virheen, MIME-/protokollaluokan, puskuroidun koon, otsakkeiden läsnäololiput ja seuraavan toimintaohjeen. Otsakkeiden arvoja tai raakavastausta ei näytetä. Tämä auttaa selvittämään myös GET400:n; aiempaa virhettä se ei palauta. Ilman --models-valintaa --diagnostics ei käynnistä mitään. Tätä verkkokomentoa ei ajettu tässä tehtävässä.

Verkkoyhteydetön `--diagnose` kertoo nyt myös key_shape_flags-lipuista (ylimääräinen Bearer, lainausmerkit, sisäinen whitespace, ei-ASCII) sekä proxy-/CA-ympäristömuuttujien **läsnäolosta**, ei arvoista. Se näyttää client- ja transport-tason trust_env=False/verify_tls=True-asetukset. HTTPTransportin aiemmin periytynyt TLS trust_env=True -oletus korjattiin kaikissa kolmessa polussa; korjausta ei esitetä400:n vahvistettuna syynä. Uusin täydellinen offline-ajo: **871 passed,2 skipped in52.45s**; eristettyjen HTTP-testien verkkosuoja estää myös vahingossa tehtävän oikean yhteyden.

### HTTP400: seuraava askel on verkkoyhteydetön diagnostiikka

Omistaja ilmoitti kahden manuaalisen testin palauttaneen HTTP400: ensin **`mistral-large-latest`**, sitten **`mistral-large-4`**. Ensimmäisestä ilmoitettiin myös `bad_request` ja `actual_billed_cost=null`. Nämä ovat omistajan raportoimia havaintoja, eivät agentin tekemiä tai uudelleen toistamia API-testejä. Omistaja ei toimittanut aiempien testien JSON-/diagnostic-tulostetta. **Uutta generointia ei ole hyväksytty; älä suorita `--live`-komentoa. Yllä oleva `--models` on erikseen sallittu vain omistajan käsin ajettavaksi tarkistukseksi. Agentti ei tee sitäkään.**

Aja nyt samassa avaimen/mallin sisältävässä PowerShellissä vain:

```powershell
.\.venv\Scripts\python.exe -m hankeluotsi.mistral_smoke --diagnose
```

Tämä tekee **0 API-/mallilistakutsua**. Se näyttää yhteenvedon: nykyisen mallin, parametrien nimet, viestien määrän/roolit,32-tokenin rajan, `stream=false`-valinnan, `Content-Type`-kuvauksen ja tunnistautumisen lähteen/skeeman. Viestisisältöjä, kokonaista pyyntörunkoa tai avain-/autentikointiotsakkeen arvoa ei tulosteta. Työtila ja avaimen kelpoisuus on merkitty varmentamattomiksi. `--preflight` pysyy aiempana niukkana asetustarkistuksena. Tarkista, että yhteenveto vastaa itse asettamaasi mallia ja yhden user-viestin32-tokenin testiä. Yhteenveto ja live käyttävät samaa puhdasta pyyntörakentajaa. Älä vaihda mallia tai nosta tokenrajaa kokeilemalla.

**Mitä voidaan päätellä:** `/v1/chat/completions`, JSON-`model`, role/content-viestilista, kokonaisluku-`max_tokens` ja boolean-`stream` vastaavat [virallista chat-kuvausta](https://docs.mistral.ai/api/endpoint/chat). Sama dokumentaatio käyttää mallia `mistral-large-latest` esimerkissä. Se ei todista aliaksen tämänhetkistä kohdemallia tai tilisi oikeutta. Oletusvastemuoto on teksti, eikä smoke lähetä JSON-skeemaa, temperature- tai reasoning-parametria. Näiden pois jättäminen ei ole osoitettu virhe.32-tokenin ylärajalle ei löytynyt yleistä kieltoa; promptin ja ulostulorajan pitää mahtua mallin kontekstiin. Tuotannon ConceptPaper-sovittimen paikallinen vähintään128-tokenin sääntö ei koske tätä erillistä probea eikä selitä palvelimen400-virhettä. Tokenrajaa tai mallia ei muutettu ilman näyttöä.

Uusi vertailu kummankin epäonnistumisen jälkeen:

| Tarkistus | Todellinen smoke-pyyntö / dokumentoitu sopimus | Johtopäätös |
| --- | --- | --- |
| Osoite ja menetelmä | POST `https://api.mistral.ai/v1/chat/completions` | Vastaa chat-endpointia; ei Azure-, Admin-, Agents- tai paikallista endpointia |
| JSON ja viestit | httpx2 `json=` tekee application/json-pyynnön; yksi user/merkkijonosisältö | Molemmilla omistajan mallinimillä mockattu wire-testi vahvistaa todellisen serialisoinnin |
| Malli | Ympäristön täsmällinen tunniste, ei fallbackia | Molemmat tunnisteet ovat dokumentoituja Large4-perheelle; kyse ei välttämättä ole kahdesta eri taustamallista |
| Ulostulo | `max_tokens=32`, integer; `stream=false`, boolean | Yleinen määrittely hyväksyy nämä kenttätyypit;32:n mallikohtaista hylkäystä ei ole todennettu |
| Muut parametrit | Ei temperature-, reasoning_effort-, response_format-, työkalu- tai connector-parametreja | Smoke ei lähetä Large4:lle kiellettyä reasoning-arvoa eikä ConceptPaper-skeemaa |
| Tunnistautuminen | Yksi `Authorization: Bearer` ja vain MISTRAL_API_KEY-ympäristöarvo; ei redirecteja/proxyjä | Otsakkeen rakenne testattu; todellinen kelpoisuus, työtila ja käyttöoikeudet eivät vahvistu400:sta |

[Mallikortti](https://docs.mistral.ai/models/mistral-large-4-0) listaa `mistral-large-4`-tunnisteen ja chat-tuen; [function calling -ohje](https://docs.mistral.ai/inference/conversations/function-calling) yhdistää Large4:n `mistral-large-latest`-aliakseen. Tämä heikentää oletusta, että pelkkä tunnisteen vaihto olisi riippumaton mallikoe. Tilin todellista aliasresoluutiota ei haettu. [Reasoning-ohje](https://docs.mistral.ai/inference/conversations/reasoning) sallii Large4:lle low/medium/high ja kieltää muun muassa none/minimal; smoke ei lähetä näitä eikä dokumentaatio osoita reasoning-asetuksen puuttumista tämän400:n syyksi. Lyhyt32-tokenin katto voi jättää ajattelevan mallin ilman lopullista vastausta, mutta se on eri havainto kuin HTTP400 eikä oikeuta budjettinostoa.

**Todennettu koodiongelma:** aiempi `--live` säilytti vain HTTP-statuksen ja yleisen `bad_request`-luokan. Palvelimen tarkka ilmoitus ei tallentunut, joten sitä ei voi palauttaa jälkikäteen tällä offline-komennolla. Pyynnön yleisen muodon ollessa kunnossa mallin/työtilan saatavuus ja mallikohtainen parametrirajoitus ovat tutkittavia mahdollisuuksia; niiden todennäköisyysjärjestystä tai tarkkaa400-syytä ei voi todistaa tästä havainnosta. Tarkista ensin [tilikonsolista](https://console.mistral.ai/) saman työtilan/API-avaimen oikeus kyseiseen chat-malliin. Älä lähetä avainta tai raakavirhettä keskusteluun. Tilin/laskutuksen tarkistus ei tarkoita uutta generointipyyntöä.

**Parannettu tuleva virhetuloste:** HTTP400/422 pitää yhteensopivan `error_code=bad_request`-arvon mutta lisää `diagnostic`-olion: kiinteä syyluokka, sallittu kenttänimi, havaintoperuste, tunnettu virhetyyppi ja kiinteät toimintaohjeet. Se tunnistaa rajatusti litteän tai sisäkkäisen virheen ja validoinnin `detail`/`message.detail`-kentät. Raakoja viestejä, parametriarvoja, syötteitä, avaimia, otsakkeita tai poikkeustekstejä ei tulosteta/tallenneta. Tunnistamaton, ei-JSON tai liian suuri virhe jää rehellisesti tuntemattomaksi. Tekstipatternit merkitään erikseen heuristiikaksi; palvelimen virhekenttä ei todista lopullista korjausta. Automaattisia uusintoja, parametrien poistoja tai budjettinostoja ei lisätty. HTTP400 ei itsessään vahvista tunnistautumista/mallipääsyä.

**Täydennetyt turvalliset virhekentät:** [Virallinen virhesopimus](https://docs.mistral.ai/resources/error-glossary) sisältää message/type/param/code-kentät. Aiempi luokittelija jätti varsinaisen `code`-kentän pois; tämä diagnostiikan puute on nyt korjattu. `diagnostic.http_status`, `provider_error_code`, `parameter` ja `sanitized_message` tallentuvat CLI:n JSON-tulosteeseen. Vain tunnetut koodinimet tai enintään5-numeroiset koodit säilytetään; tuntemattomat/arveluttavat arvot peitetään. `parameter` sisältää vain palvelimen ilmoittaman sallitun kentän, kun taas vanha `field` voi olla päätelty. Esimerkiksi pelkkä invalid_model-tyyppi ei keksi `parameter=model`-havaintoa. Viesti rakennetaan tunnistetusta virhelauseesta uudelleen: mallinimi, sähköpostit, polut, projektiteksti, tunnisteet ja muut vapaat arvot peitetään. Tunnettu numeerinen tokenrajoitus voidaan säilyttää lyhyenä tarkistettavana väitteenä. `message_sanitization` kertoo allowlist-muunnoksesta, peittämisestä tai puuttuvasta viestistä; tämä ei ole alkuperäisen viestin sanatarkka kopio. Avain peitetään jo ennen tunnistamista, myös koodi-/numerokentässä. Tuntemattomia provider-koodeja ei väitetä tunnetuiksi. Nykyinen `--diagnose` ei lue tai palauta vanhoja virhevastaustietoja.

`actual_billed_cost=null` on edelleen **tuntematon**, ei nollahinta tai laskutuksen puuttumisen todiste; alkuperäinen komento ei saanut laskutietoa rajapinnasta. Toteutunut veloitus tarkistetaan tililtä. Kohdennetut uudet offline-regressiot:145 passed in2.63s (mockatut vastaukset); ei uutta live-kutsua. Turvallisin seuraava toimi on tarkistaa nykyinen pyyntö offline sekä tilikonsolista juuri käytetyn inference-avaimen aktiivinen työtila, mallioikeudet ja mahdolliset jo tehtyjen pyyntöjen virhetiedot. Yhteinen malli-/työtilakonteksti tai mallikohtainen rajoitus on työhypoteesi; tarkkaa juurisyytä ei voi vahvistaa ilman jo tehdyn pyynnön palvelinvirheen tietoja. Kolmatta mallia, budjettinostoa tai uutta API-testiä ei suositella tämän offline-tehtävän jatkona.

### Lyhyt yhteystesti: `--live`

**Tuotantosovittimen täydennys:** turvallinen virheparseri on nyt yhteinen `mistral_client.py`:ssä. Varsinainen MistralTransport säilyttää suodatetut virhetiedot CloudErrorissa, ja molemmat smoke-polut käyttävät niitä. Viestin enimmäispituus on240 merkkiä ja virhe-JSONin parsintaraja64 KiB; poikkeuksen yleinen käyttöliittymäteksti pysyy ennallaan. Suorat httpx2/certifi-riippuvuudet on ilmoitettu. Katso [tarkka korjaus ja koko offline-testin tulokset](mistral_diagnosis.md). Tämä ei palauta aiempia kadonneita virherunkoja eikä vahvista live-yhteyttä.

Omistajan myöhempi pyyntö yksinkertaisti ensimmäisen manuaalisen yhteystestin yhdeksi komennoksi. Aja se **kerran projektihakemistossa samasta PowerShellistä, jossa `MISTRAL_API_KEY` ja tilillä hyväksytty `MISTRAL_MODEL` ovat jo asetettuina**:

```powershell
.\.venv\Scripts\python.exe -m hankeluotsi.mistral_smoke --live
```

`--live` on nimenomainen valinta yhdelle mahdollisesti laskutettavalle yhteystestille; uutta ajoa varten tarvitaan omistajan erillinen hyväksyntä. Kiinteä lyhyt fiktiivinen Meadow-kehote käyttää nyt oletuksena enintään256 ulostulotokenia ja60s HTTP-vaiheaikakatkaisua. `--max-output-tokens` sallii vain32/128/256/512;32 palauttaa historiallisen katon. Vain yksi POST, ei uusintoja, automaattista budjetin nostoa, uudelleenohjauksia, mallilistakutsuja, benchmarkia tai tiedosto-/tietokantakirjoituksia. Mallia ei arvata eikä vaihdeta. Puuttuva avain/malli estää pyynnön. Agentti ei suorittanut tätä komentoa; testit käyttivät mockattua HTTP:tä.

Tulostuva JSON sisältää HTTP-statuksen, `api_request_succeeded`-tiedon (HTTP2xx, ei yksin kelvollinen vastaus), lopullisen tekstin olemassaolon, valmistumissyyn ja raportoidut tokenmäärät. `outcome=http_api_error` eroaa `output_token_limit`- ja `context_limit`-tuloksista; katkeaminen ja tokenkaton saavuttaminen raportoidaan erikseen. Avainta, tekstiä, raakavirheitä tai otsakkeita ei tulosteta. `success=true` edellyttää ei-tyhjää lopullista tekstiä ja `finish_reason=stop`; se voi onnistua täsmälleen tokenkatolla. Tuntematon valmistumissyy jää varmentamattomaksi. Tuntematon hinta jää null; todellinen veloitus tarkistetaan tililtä. Paluukoodi0 tarkoittaa valmista vastausta,1 yhden yrityksen epäonnistumista/myös onnistuneen API-pyynnön katkennutta vastausta ja2 puuttuvaa konfiguraatiota/virheellisiä valintoja. Aikakatkaisu ei todista, ettei palveluntarjoaja laskuttanut pyyntöä.

Tämä mittaa lyhyen tekstivastauksen yhteyttä. Alkuperäinen512-tokenin ConceptPaper-/skeematesti säilyy alla erillisenä vaihtoehtona; sitä ei ajeta `--live`-valinnalla. Oletus ja `--preflight` ovat edelleen verkkoyhteydettömiä. `--live`-valintaa ei voi yhdistää muihin ajotiloihin tai tulostiedostovalintoihin.

### Alkuperäinen ConceptPaper-testi ja ympäristön tarkistus

**Älä suorita maksullista komentoa ennen omistajan hyväksyntää sekä mallioikeuden, hinnan ja saldon varmistusta.** Esitarkistus ja alla oleva pelkkä ympäristön UI-tarkistus eivät tee mallipyyntöjä.

1. Käytä samaa jo avaimen sisältävää PowerShell-ikkunaa projektihakemistossa. Avainta ei tarvitse kopioida tähän keskusteluun tai tiedostoon. Aja:

```powershell
.\.venv\Scripts\python.exe -m hankeluotsi.mistral_smoke --preflight
```

`configured=true` tarkoittaa vain, että tämä lapsiprosessi sai avaimen ja syntaktisesti kelvollisen mallimuuttujan. Se ei varmista mallin käyttöoikeutta eikä hintaa. Jos mallimuuttuja puuttuu, aseta vain tililläsi hyväksytty täsmällinen tunniste; mitään oletusmallia ei tarjota:

```powershell
if (-not $env:MISTRAL_MODEL) {
    $env:MISTRAL_MODEL = Read-Host 'Tilillä hyväksytty täsmällinen Mistral-mallin tunniste'
}
```

Jos avain puuttuu, et ole sitä sisältävässä istunnossa tai nykyistä muuttujaa ei ole asetettu. Älä tulosta sitä tai lue toisen prosessin muistia. Tarvittaessa käytä [suojattua asetusohjetta](mistral_setup.md).

2. Varmista, että **käynnistyvä Streamlit-prosessi** perii samat muuttujat. Tämä erillinen demoinstanssi käyttää uutta väliaikaista tietokantaa ja palauttaa aiemman tietokantamuuttujan lopuksi:

```powershell
$previousDemoDbPath = $env:HANKELUOTSI_DB_PATH
$env:HANKELUOTSI_DB_PATH = Join-Path $env:TEMP ("hankeluotsi-mistral-check-" + [guid]::NewGuid().ToString('N') + '.sqlite3')
try {
    .\.venv\Scripts\python.exe -m streamlit run app.py --server.address=127.0.0.1 --server.port=8502
} finally {
    if ($null -eq $previousDemoDbPath) { Remove-Item Env:HANKELUOTSI_DB_PATH -ErrorAction SilentlyContinue }
    else { $env:HANKELUOTSI_DB_PATH = $previousDemoDbPath }
}
```

Avaa `http://localhost:8502`, valitse01-vaiheen generointipalveluksi Mistral. Mallin konfiguraatioteksti ja käytettävissä oleva, edelleen rastittamaton suostumusruutu osoittavat konfiguraation löytymisen **tässä Streamlit-prosessissa**. Puuttuva asetus näyttää vastaavan ohjeen. Älä paina Generate-painiketta tätä tarkistusta varten. Sulje demopalvelin Ctrl+C:llä samassa PowerShellissä; avain jää sen ympäristöön. Älä käynnistä porttiin toista päällekkäistä palvelinta.

3. Tarkista [Mistralin tilikonsolista](https://console.mistral.ai/) valitun mallin chat/custom-schema-oikeus, saldo, käyttörajat ja [ajantasainen API-hinnasto](https://docs.mistral.ai/inference/pricing). Smoke käyttää vain tekstiä,512 ulostulotokenia,0.2 lämpötilaa ja120s HTTP-vaiheaikakatkaisua. Käytä varmistettua input-tokenien ylärajaa `N` ja saman valuutan input/output-hintoja per miljoona tokenia konservatiiviseen rajaan `(N × input_hinta + 512 × output_hinta) / 1000000`. Dokumentoitu mallin kontekstiraja voi toimia väljänä input-ylärajana. Jos luotettavaa ylärajaa/hintaa ei saada, älä suorita pyyntöä. Budjettirajan olemassaolo ei todista saldoa tai pyyntökohtaista hintaa.

4. Hyväksynnän jälkeen aja samasta PowerShellistä **kerran**, uuteen hakemistoon:

```powershell
.\.venv\Scripts\python.exe -m hankeluotsi.mistral_smoke `
  --execute-cloud --fictional-only --accept-costs `
  --output .benchmark-private/mistral-single-owner-01
```

Tämä tekee enintään yhden generointipyynnön Q01-fiktiosta, ilman mallilista-, lämmittely-, korjaus- tai uusintapyyntöjä ja ilman SQLitea. Se käyttää oikeaa ConceptPaper-sopimusta ja nykyistä compact-kehotetta. Hakemistoa ei saa käyttää uudelleen. `request.json` tallentaa kehotteen, skeeman, rajat ja lähdehashit ilman autentikointiotsakkeita; `receipt.json` sisältää turvalliset tulokset/metatiedot ja onnistumisessa `concept.json` validoidun konseptin.

Mahdollinen valinnainen `--pricing .benchmark-private/pricing-owner.json` käyttää olemassa olevaa omistajan tarkistamaa `model_quality.Pricing`-muotoa. Ilman sitä kuluarvio jää null; hinnan manuaalinen hyväksyntä tarvitaan silti ennen pyyntöä. Saldoa tai todellista veloitusta ei päätellä tokenmäärästä. Oletusarvoinen lyhyt512-tokenin raja voi katkaista erityisesti ajattelevaa mallia; epäonnistuminen ei oikeuta automaattiseen toistoon tai hiljaiseen mallin vaihtoon.

5. Tarkista yksityisestä kuitista `success`, `finish_reason`, JSON/Pydantic, raportoitu malli, käyttömäärät ja mahdollinen virheluokka. Tarkista tililtä toteutunut veloitus. Aikakatkaisu ei todista palvelinlaskennan tai laskutuksen loppuneen. Älä aloita täyttä maksullista vertailua tai uusintaa ilman erillistä päätöstä.

## Testitulokset ja prototyypin rajaus

Viimeinen koko offline-ajo: **703 passed,2 skipped,51.80s**, komento `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider`, live-rahoitushaku pois, uusi väliaikainen oletus-SQLite ja bytecode-kirjoitus pois. Ohitukset ovat erikseen sallittavia julkisten lähteiden verkkotestejä. `git diff --check` ja säilytystarkistukset kirjataan kehityslokiin.

Mockattu HTTP-testi käy oikeiden MistralClient/StageClient/WorkflowService/UI/repository-polkujen kautta kaikki kolme generointivaihetta FI/EN, sitten hyväksynnän/viennin. Lisäksi testataan virheluokat, puuttuvat asetukset, aikakatkaisu, JSON/skeema, katkeaminen, tekstiosat, provider-vaihto, suostumukset, vanhentunut lähde ja hyväksyttyjen tietojen säilyminen. Oikea Edge-selain varmisti uuden kehote-/huomiokoodin kanssa nykyisen navigoinnin, hyväksynnän ja todelliset Markdown-lataukset valmiista fiktiivisistä luonnoksista ilman mallikutsuja.

Prototyypin tarkistettavaksi sopivat sovittimen turvaparannukset, takautuvasti yhteensopivat ohjeelliset huomiot, versioidut kehotteet, testit ja eristetty offline-benchmark. Kehotteiden vaikutus Qwenin/mallikohtaisen skeematuen nopeuteen ja sisällön laatuun on vielä mitattava; Mistralin live-yhteyttä ei merkitä valmiiksi ennen hyväksyttyä smokea. Ammatillinen ihmisarvio, vaihekohtainen luotettavuusportti ja varsinainen vertailutulos puuttuvat. Olemassa olevia tietueita, skeemoja, avaimia, alkuperäisiä tuloksia tai mallivalintoja ei muutettu. Ei commitia, pushia tai mergeä.
