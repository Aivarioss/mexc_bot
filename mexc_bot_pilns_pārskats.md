+# 🤖 MEXC Trading Bot — Arhitektūras Pārskats (v2.1)

*Atjaunināts: 2025-04-01*

---

## 📁 Mapes struktūra

```text
mexc_bot/
├── main.py                   ← Galvenais bots: skenē, analizē, pērk
├── tracker_loop.py           ← Uzrauga aktīvās pozīcijas (TP/SL)
├── telegram_loop.py          ← Telegram komandu listeners (polling)
├── collect_all_data.py       ← Savāc visus simbolus no MEXC (viens skrējiens)
├── collect_and_save.py       ← Saglabā tokena datus (OHLCV)
├── train_all_models.py       ← Apmāca visus CSV failus (AI)
├── train_pending_models.py   ← Apmāca tikai tos, kuriem nav modeļa
├── train_from_labeled.py     ← Trenē globālo AI modeli no breakout tokeniem
├── label_candidates.py       ← Apzīmē hype tokenus pēc 6h izaugsmes
├── cleanup.py                ← Dzēš vecos CSV failus (>3 dienas)
├── report.py                 ← Statistikas atskaite par darījumiem
├── start_telegram.bat        ← Palaid Telegram listeneri (Windows)
├── stop_telegram.bat         ← Apstādina Telegram listeneri (Windows)
├── train.bat                 ← BAT fails AI treniņam (Windows)
├── trade.bat                 ← BAT fails galvenā bota palaišanai
├── clearmodels.py            ← Notīra vecos modeļus,ja pievieno jaunus indikatorus
├── cleartestdata.py          ← Notīra vecos Test datus

├── config/
   └── settings.py           ← Visi konfigurācijas parametri 
   └── config/state.json          ← Pārslēdz test on off

├── data/
│   ├── market_data/           ← OHLCV CSV dati (viens fails = viens tokens)
│   ├── tracked_tokens.json    ← Aktīvās pozīcijas (TP/SL uzraudzība)
│   ├── trade_history.json     ← Visi veikti darījumi (buy/sell)
│   ├── summary_log.json       ← Dienas kopsavilkumu vēsture
│   ├── bot_log.json           ← AI aktivitātes žurnāls
│   ├── pending_training.json  ← Tokeni, kam vēl nav modeļa
│   ├── candidate_tokens.csv   ← Kandidāti AI treniņam / pēctreniņa analīzei
│   └── labeled_candidates.csv ← Apzīmēti breakout tokeni pēc 6h 
│   └──	test_log.json          ← Test Ai aktivitātes žurnāls	
│   └──	test_trade_history.json← Test veiktie darījumi
│   └── test_summary_log.json  ← Test kopsavilkumu vēsture
│   └── trade_summary.py       ← pieprasa trade datus
│   └── testtrade_summary.py   ← pieprasa test trade datus
│   └── test_tracked_tokens.json← test aktīvā uzraudzība
│   └── volatility_log.json     ←vojalitātes dati
		
├── models/
│   ├── SYMBOL_model.pkl       ← Individuālais AI modelis
│   ├── SYMBOL_scaler.pkl      ← Skaleris konkrētajam tokenam
│   ├── SYMBOL_features.pkl    ← Feature saraksts tokenam
│   ├── feedback_model.pkl     ← Globālais breakout modelis
│   ├── feedback_scaler.pkl    ← Skaleris globālajam modelim
│   └── feedback_features.pkl  ← Feature saraksts globālajam AI

├── modules/
│   ├── ai_predictor.py        ← AI filtrs tokeniem (predikcija)
│   ├── ai_trainer.py          ← Modeļu treniņa loģika (token / globālais)
│   ├── token_filter.py        ← Stratēģijas noteikšana (simple/aggressive)
│   ├── trade_executor.py      ← Veic pirkumus + saglabā tracked
│   ├── mexc_fetcher.py        ← Nolasīšana no MEXC API
│   ├── price_tracker.py       ← TP/SL/ATR menedžeris. Labojums, pārejam pagaidām neaktīvs, pārejam uz vienu loop ciklu
│   ├── symbol_checker.py      ← Simbola validācija biržā
│   └── collect_and_save.py    ← CSV datu saglabāšana + pending
│   └── adaptive_trade_helper.py← ģenerē adaptīvi TP SL
│   └── market_sentiment.py    ←pielāgo settingus pēc tirgus noskaņojuma, filtrē btc/usdt cenu izmaiņas
│
└── utils/
    ├── data_helpers.py        ← Sagatavo datus modeļiem
    ├── file_helpers.py        ← JSON helperi (load/save)
    ├── indicators.py          ← RSI, MACD, BB, ATR u.c.
    ├── telegram_alerts.py     ← Telegram ziņu sūtīšana
    ├── telegram_commands.py   ← Telegram komandu apstrāde
    ├── trade_logger.py        ← Saglabā buy/sell darījumus
    ├── save_candidate.py      ← Saglabā tokenus, ko AI atmeta
    ├── summary.py             ← /activity atskaite par AI
    └── tracking.py            ← /resync, /tracked, /cleartracked u.c.
    └── volatility_logger.py   ← vojalitātes saglabāšana
	└── cleanup.py             ← Dzēš vecos CSV failus (>3 dienas)
```
---

## 🔄 Procesu plūsma (`main.py`)

1. Skenē MEXC tirgu
2. Atlasa "hype" tokenus (pēc cenas, apjoma, % izaugsmes)
3. Klasificē stratēģiju: `simple`, `aggressive`, `revival`
4. Ja `strategy` ir `simple` vai `revival`, sākas AI filtrēšana
5. Pirmā pārbaude: globālais `feedback_model.pkl`
6. Ja tas atgriež `True`, pārbauda individuālo modeli
7. Ja nav individuālā modeļa → trenē un saglabā
8. Ja AI dod "zaļo gaismu" → veic pirkumu
9. Token pievienots `tracked_tokens.json`, sāk TP/SL sekošana

---

## 🧠 Modeļu apmācība

| Skripts                  | Funkcija |
|--------------------------|----------|
| `train_all_models.py`    | Apmāca visus CSV failus (tokenus) |
| `train_pending_models.py`| Apmāca tikai tos, kam vēl nav modeļa |
| `train_from_labeled.py`  | Trenē *globālo feedback modeli* (reāli breakout tokeni) |
| `main.py`                | Trenē modeļus uz vietas, ja nav pieejami |

---

## 📊 Modeļu faili

```text
models/
├── PEPEUSDT_model.pkl        ← Individuālais modelis
├── PEPEUSDT_scaler.pkl       ← Skaleris konkrētajam tokenam
├── PEPEUSDT_features.pkl     ← Feature saraksts konkrētajam modelim
├── feedback_model.pkl        ← Globālais breakout AI modelis
├── feedback_scaler.pkl       ← Skaleris globālajam modelim
├── feedback_features.pkl     ← Feature saraksts globālajam AI
```

---

## 📦 Datu faili

```text
data/
├── tracked_tokens.json      ← Aktīvās pozīcijas ar TP/SL
├── trade_history.json       ← Visi veikti darījumi
├── pending_training.json    ← Tokeni bez AI modeļa
├── candidate_tokens.csv     ← Tokeni, ko AI atmeta
├── labeled_candidates.csv   ← Pēc 6h apzīmēti breakout tokeni
├── summary_log.json         ← Dienas kopsavilkumi
├── bot_log.json             ← AI darbības un kļūdas
├──	test_log.json 			 ← Test Ai aktivitātes žurnāls	
├──	test_trade_history.json  ← Test veiktie darījumi```
└── test_summary_log.json    ← Test kopsavilkumu vēsture
└── test_tracked_tokens      ← test aktīvā uzraudzība
---

## 📢 Telegram komandas

| Komanda           | Funkcija |
|-------------------|----------|
| `/startbot`       | Startē `main.py` un `tracker_loop.py` |
| `/stopbot`        | Aptur abus procesus |
| `/stopall         | Aptur visus procesus, ztstā telegramloo|
| `/restartbot`     | Restartē botu |
| `/restarloop`     | Restartē telegramloop |
| `/starttrain`     | Startē treniņu skriptus (`train.bat`) |
| `/stoptrain`      | Aptur treniņu |
| `/retrainfeedback`| Trenē globālo feedback AI modeli |
| `/summary`        | Tirdzniecības kopsavilkums |
| `/testsummary`    | TestTirdzniecības kopsavilkums |
| `/activity`       | AI aktivitātes žurnāls |
| `/testactivity`   | TestAI aktivitātes žurnāls |
| `/resync`         | Atjauno tracked tokenus no vēstures |
| `/tracked`        | Parāda aktīvās pozīcijas |
| `/cleartracked`   | Noņem tokenus, kuru tev vairs nav |
| `/balance`        | Parāda USDT bilanci biržā |
| `/cleanup`        | Dzēš vecos CSV failus (>3 dienas) |
| `/status`         | Aktīvie Python procesi |
| `/ping`           | Vai bots darbojas? |
| `/help`           | Komandu saraksts |
| `/testmode_on     | ieslēdz testēšanas režīmu
| `/testmode_off    | izslēdz testēšanas režīmu
| `/teststatus      | parāda, vai TEST_MODE ir aktīvs
| `/testtracked`    | Parāda test aktīvās pozīcijas |
| `/clearmodels     | Notīra modeļus,ja pievieno jaunus indikatorus
| `/cleartestdata   | Notīra vecos Test datus 


---

## 🔒 TP/SL + ATR uzraudzība

Generē adaptīvu TP/SL
- Izpilde notiek `tracker_loop.py`
# 📜 CHANGELOG — MEXC Trading Bot

## [v2.2] — 2025-04-25
### Uzlabojumi:
- ✨ **ATR-based Stop-Loss korekcija**:
  - Stop-Loss līmenis tiek dinamiski pielāgots atkarībā no volatilitātes (ATR/price attiecība).
  - Augsta volatilitāte ➔ plašāks SL. Zema volatilitāte ➔ stingrāks SL.

- ✨ **Dynamic Trailing Take-Profit režīms**:
  - Pēc visu TP līmeņu sasniegšanas tiek sekots jaunam augstākajam cenai.
  - Ja cena krīt par 3% no maksimuma ➔ tiek veikta pilna pārdošana.

- ✨ **Scaling-out daļējās pārdošanas uzlabošana**:
  - TP daļējā pārdošana pielāgota pēc AI confidence.
    - Confidence ≥ 0.95 ➔ ilgāka pozīcijas turēšana (lēnāka pārdošana).
    - Confidence ≤ 0.85 ➔ ātrāka daļēja iziešana.

- ✨ **Dynamic Peak Tracking**:
  - Katram tokenam saglabājam dinamisko maksimumu (`dynamic_peak`), lai precīzāk pārvaldītu trailing TP režīmu.


---



# 📊 Preview: TP/SL Līmeņi pēc confidence un stratēģijas

strat_data = {
    "confidence": [0.8, 0.85, 0.9, 0.95],
    "simple":    {"tp": [[1.03, 1.06, 1.09], [1.05, 1.10, 1.20], [1.05, 1.10, 1.20], [1.10, 1.20, 1.30, 1.40]],
                  "sl": [0.025, 0.035, 0.035, 0.05]},
    "aggressive":{"tp": [[1.236, 1.272, 1.308], [1.26, 1.32, 1.44], [1.26, 1.32, 1.44], [1.32, 1.44, 1.56, 1.68]],
                  "sl": [0.03, 0.042, 0.042, 0.06]},
    "revival":  {"tp": [[0.927, 0.954, 0.981], [0.945, 0.99, 1.08], [0.945, 0.99, 1.08], [0.99, 1.08, 1.17, 1.26]],
                  "sl": [0.0225, 0.0315, 0.0315, 0.045]},
    "momentum_safe": {"tp": [[1.059, 1.091, 1.143], [1.1025, 1.155, 1.26], [1.1025, 1.155, 1.26], [1.155, 1.26, 1.365, 1.47]],
                      "sl": [0.021, 0.028, 0.028, 0.04]},
}




---

## 🔁 Feedback AI Process

1. Token tiek atgriezts kā nederīgs → saglabā `candidate_tokens.csv`
2. Pēc 6h `label_candidates.py` aprēķina reālo izaugsmi un piešķir `label`
3. Labeled dati tiek izmantoti `train_from_labeled.py`, lai uztrenētu `feedback_model.pkl`
4. Globālais AI modelis filtrē breakout līdzīgos tokenus pirms individuālā modeļa
5. Ja modelis saka “Yes” → tiek izmantots tālākējais AI/stratēģijas cikls

01.04 pivienota test versija



🔁 Datu vākšana	OHLCV datu vākšana	collect_all_data.py / collect_and_save.py	data/market_data/*.csv
🔎 Tokenu analīze	Meklē "hype" tokenus + AI/feedback filtrs	main.py	-
❌ Atmesto tokenu saglabāšana	Kandidāti, kas noraidīti	save_candidate.py	data/candidate_tokens.csv
🏷️ Marķēšana (labeling)	Pēc 6h uzliek "label" (1 = >5% pieaugums)	label_candidates.py	data/labeled_candidates.csv
📥 Apmācāmie tokeni	Tiek atlasīti tokeni ar label = 1	-	data/pending_training.json
📥 1. Datu vākšana
→ collect_all_data.py
Automātiski vāc OHLCV datus no MEXC biržas
⬇️
Saglabā CSV failus šeit: data/market_data/*.csv

→ collect_and_save.py
Manuāli vāc konkrēta simbola datus + pievieno pending_training.json

🔍 2. Kandidātu atlase (reālā laikā)
→ main.py

Izsauc get_hype_tokens()

AI filtrēšana caur ai_filter() (ai_predictor.py)

Ja AI noraida → save_candidate.py saglabā data/candidate_tokens.csv

Ja AI atļauj → is_feedback_model_positive() (feedback_predictor.py)

Ja arī feedback apstiprina → Buy (vai log_test_trade() test režīmā)

🧾 3. Noraidīto kandidātu reģistrs
→ save_candidate.py
📄 Raksta tokena info uz: data/candidate_tokens.csv

🏷️ 4. Labelēšana pēc 6h
→ label_candidates.py

Pārbauda cenas izmaiņu pēc 6h

Pievieno label = 1, ja pieaugums ≥ 5%
⬇️

Saglabā uz data/labeled_candidates.csv

Tokenus ar label=1 pievieno pending_training.json

🧠 5. AI modeļu apmācība (katram tokenam)
→ train_pending_models.py

Iet cauri simboliem no pending_training.json

Izsauc train_ai_model() (ai_trainer.py)

→ train_all_models.py

Iet cauri visiem CSV failiem market_data/

Apmāca, ja modelis vēl neeksistē

📦 6. Saglabātie modeļi
Katram tokenam:

models/BTC_USDT_model.pkl

models/BTC_USDT_scaler.pkl

models/BTC_USDT_features.pkl

🧠 7. Feedback modelis (globāls, uz visiem datiem)
→ train_feedback_model.py

Apmāca no labeled_candidates.csv

Saglabā:

models/feedback_model.pkl

feedback_scaler.pkl

feedback_features.pkl

→ feedback_predictor.py

Izmanto treniņā sagatavoto modelīti reālā laikā

Prognozē: vai token vērts pirkt (vērtība 0–1)

1. collect_all_data.py / collect_and_save.py → market_data/*.csv
2. main.py → ai_filter (ai_predictor.py)
   ├─→ save_candidate.py → candidate_tokens.csv
   └─→ feedback_predictor.py → OK?
        ├─→ Buy
        └─→ save_candidate.py (ja noraidīts)
3. label_candidates.py → pēc 6h → labeled_candidates.csv + pending_training.json
4. train_pending_models.py / train_all_models.py → ai_trainer.py → models/
5. train_feedback_model.py → feedback_model.pkl

