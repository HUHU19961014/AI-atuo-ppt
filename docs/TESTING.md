# Testing

## Local Quality Gate (CI-aligned)

Run the local CI-aligned gate:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\quality_gate.ps1
```

Execution order:

1. Targeted `ruff --select F` checks (same scope as CI quality-gates).
2. Targeted `mypy` checks (release target files only).
3. Legacy boundary guard (`tools/check_legacy_boundary.py`).
4. Release subset test suite.
5. Coverage gate for CLI entry surfaces (`--fail-under=80`).

## Performance And Concurrency Checks

- Long-run stress batching (120-slide synthetic input):

```powershell
python .\tools\stress_test_v2.py
```

- Timeout graceful degradation check:

```powershell
python .\main.py v2-make --topic "timeout fallback check" --graceful-timeout-fallback
```

- Concurrent output collision isolation:

```powershell
python .\main.py v2-make --topic "run A" --isolate-output --run-id run-a
python .\main.py v2-make --topic "run B" --isolate-output --run-id run-b
```

`SIE-autoppt` 褰撳墠寤鸿鍒嗘垚 4 绫讳富娴嬭瘯涓?1 绫绘潯浠舵€у吋瀹规祴璇曪細

1. 鍗曞厓娴嬭瘯
2. 杞婚噺闆嗘垚娴嬭瘯
3. `python .\main.py make --topic "test smoke"` 鏃?AI 鍐掔儫鍥炲綊
4. `tools/v2_regression_check.ps1` V2 deck 鍥炲綊
5. 鍏煎娴嬭瘯锛歚tools/legacy_html_regression_check.ps1` legacy HTML 鏍蜂緥鍥炲綊

## 鍩虹嚎鍘熷垯

- 鍙娴嬭瘯浼氳惤鍒板疄闄呮覆鏌撱€佽瑙夋鏌ャ€佸彂甯冮獙鏀讹紝灏变紭鍏堜娇鐢ㄤ粨搴撳唴鐨?SIE 妯℃澘鍩虹嚎锛歚assets/templates/sie_template.pptx`銆?
- 鐢熶骇閾捐矾涓婚鍥哄畾涓?`sie_consulting_fixed`锛涙祴璇曟牱渚嬪鏋滀娇鐢ㄥ叾浠栦富棰橈紝浠呭彲鐢ㄤ簬鍏煎/瀹為獙锛屼笉浣滀负涓诲洖褰掔鏀朵緷鎹€?
- 鍏朵粬 theme銆佸閮ㄦā鏉裤€佸弬鑰冩牱寮忔洿閫傚悎浣滀负琛ュ厖瑕嗙洊锛屼笉搴旀浛浠?SIE 妯℃澘鐨勪富鍥炲綊銆?
- 濡傛灉鏌愭潯娴嬭瘯娌℃湁鐩存帴鏄惧紡浼犳ā鏉匡紝涔熷簲纭瀹冩渶缁堣蛋鐨勬槸褰撳墠榛樿鐨?SIE 妯℃澘閾捐矾銆?

## 褰撳墠纭棬绂侊紙娴嬭瘯蹇呴』瑕嗙洊锛?

- 涓婚蹇呴』涓?`sie_consulting_fixed`
- 鐩綍寮忔爣棰橈紙渚嬪鈥滃缓璁捐儗鏅€濃€滅幇鐘朵粙缁嶁€濓級鎸夐敊璇骇鍒鐞?
- `title_content` 瑕佺偣鏁伴噺蹇呴』鍦?`1-6` 涔嬮棿

## 鎺ㄨ崘瀹夎

浼樺厛浣跨敤鍙畨瑁呭寘鏂瑰紡锛?

```bash
python -m venv .venv
. .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

濡傛灉鍙蛋鍏煎璺緞锛?

```bash
python -m pip install -r requirements.txt
python -m pip install pytest
```

## 鑷姩鍖栭儴鍒?

杩欎簺鍙互鐩存帴鐢变唬鐮佸拰鏈満鐜瀹屾垚锛屼笉闇€瑕佷汉宸ラ€愰〉纭锛?

- HTML 瑙ｆ瀽涓庤緭鍏ユ牎楠?
- Deck planning 涓庣珷鑺傞挸鍒?
- 妯℃澘 manifest 鍔犺浇
- 鏈€灏忕敓鎴愰摼璺?
- 鏉′欢鎬?`QA.txt` / `QA.json` 缁撴瀯涓庡叧閿瓧娈?
- `make` 鏃?API 鍐掔儫璺緞

浼樺厛杩愯鏂瑰紡锛?

```bash
python -m pytest tests -q
```

鍏煎杩愯鏂瑰紡锛?

```bash
python -m unittest discover -s tests -v
```

PowerShell 蹇嵎鍏ュ彛锛?

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_unit_tests.ps1
```

鎺ㄨ崘鍏堣窇鐨勪富璺緞妫€鏌ワ細

```powershell
python -m pytest tests -q
python .\main.py make --topic "test smoke"
powershell -ExecutionPolicy Bypass -File .\tools\v2_regression_check.ps1
```

杩欎簺涓昏矾寰勬鏌ュ簲榛樿瑙嗕负 SIE 妯℃澘鍩虹嚎鍥炲綊銆?

鍙€夌湡瀹?AI 灏忔牱鏈洖褰掞細

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run_real_ai_smoke.ps1
```

璇存槑锛?

- 杩欎釜 smoke test 榛樿涓嶅弬涓庡父瑙勫洖褰掞紝鍙湁鏄惧紡璁剧疆 `OPENAI_API_KEY` 骞惰繍琛岃剼鏈椂鎵嶆墽琛屻€?
- 榛樿浣跨敤 `quick` 妯″紡鎺у埗鎴愭湰鍜屾椂寤讹紱濡傞渶鏇存帴杩戞寮忎富閾捐矾锛屽彲浼?`-GenerationMode deep`銆?
- 濡傞渶鎶?smoke test 璺戝埌瀹為檯 PPT 娓叉煋闃舵锛屽彲浼?`-WithRender`锛屼絾杩欎細澧炲姞鑰楁椂鍜屾湰鏈轰緷璧栥€?

鍏煎灞傚洖褰掞紝浠呭湪淇敼 legacy HTML/template 璺緞鏃堕渶瑕侊細

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\legacy_html_regression_check.ps1
```

## 闇€瑕佷汉宸ラ厤鍚堢殑閮ㄥ垎

杩欎簺娴嬭瘯涓嶉€傚悎瀹屽叏鑷姩鍖栵紝鎴栬€呰嚦灏戝湪褰撳墠闃舵涓嶅€煎緱浼樺厛鑷姩鍖栵細

- 妯℃澘鎹㈢増鍚庣殑瑙嗚楠屾敹
- 鏂颁笟鍔℃牱渚嬫槸鍚︹€滆寰楀銆佹帓寰楅『鈥?
- 涓嶅悓妯℃澘鏄惁宸茬粡杩佺Щ鍒?preallocated slide pool
- 鏈€缁堜氦浠樺墠鐨勯粍閲戞牱渚嬫娊妫€

寤鸿鏈€灏戜繚鐣?3 涓粍閲戞牱渚嬪仛浜虹溂楠屾敹锛?

- 閫氱敤涓氬姟椤?
- ERP / 鏋舵瀯椤?
- 鍙傝€冩牱寮忓鍏ラ〉

## 杩愯鏃舵敞鎰忎簨椤?

- `legacy clone` 璺緞宸茬粡鏍囪涓?deprecated锛屼粎鐢ㄤ簬娌℃湁 slide pool 鐨勬棫妯℃澘鍏滃簳
- 濡傛灉 legacy clone 鐩綍椤佃祫婧愪慨澶嶈繛缁け璐ワ紝鐢熸垚娴佺▼浼氭槑纭姤閿欙紝鑰屼笉鏄潤榛樼户缁?
- 鏂版ā鏉垮簲浼樺厛缁存姢 `manifest.slide_pools`

鍙洿鎺ョ敓鎴愯瑙夐獙鏀舵壒娆★細

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\prepare_visual_review.ps1
```

璇存槑锛?

- `prepare_visual_review.ps1` 灞炰簬鍐呴儴杈呭姪鑴氭湰锛屼笉鏄櫘閫氱敤鎴蜂富璺緞銆?
- 瀹冧細浣跨敤浠撳簱鍐呯疆鐨?V2 `deck.json` 鍥炲綊鏍蜂緥锛岃€屼笉鏄棫鐨?HTML 鏍蜂緥銆?
- 杩欐壒瑙嗚楠屾敹榛樿涔熷簲浠ュ綋鍓?SIE 妯℃澘杈撳嚭浣滀负绛炬敹鍩虹嚎銆?
- 瑙嗚澶嶆牳鑻ユ嬁涓嶅埌 PNG 棰勮锛屼細閫€鍖栨垚鍩轰簬 Deck 鍐呭鐨勪繚瀹堣瘎瀹°€?

浜哄伐楠屾敹璇存槑瑙?[docs/HUMAN_VISUAL_QA.md](./HUMAN_VISUAL_QA.md)銆?

## 褰撳墠娴嬭瘯鍏ュ彛

- 鍗曞厓涓庤交闆嗘垚娴嬭瘯锛歚tests/`
- 鑷姩鍖栬繍琛屽叆鍙ｏ細[tools/run_unit_tests.ps1](../tools/run_unit_tests.ps1)
- V2 鍥炲綊鍏ュ彛锛歔tools/v2_regression_check.ps1](../tools/v2_regression_check.ps1)
- 鐪熷疄 AI smoke 鍏ュ彛锛堟寜闇€鎵ц锛夛細[tools/run_real_ai_smoke.ps1](../tools/run_real_ai_smoke.ps1)
- Legacy HTML 鍥炲綊鍏ュ彛锛堝吋瀹瑰眰锛屼粎鎸夐渶鎵ц锛夛細[tools/legacy_html_regression_check.ps1](../tools/legacy_html_regression_check.ps1)


## Real AI Golden Dataset

Optional real-model baseline:

`powershell
='1'
='sk-...'
python -m pytest tests/test_real_ai_golden_dataset.py -q
`

Dataset file: egression/real_ai_golden_dataset.json.

