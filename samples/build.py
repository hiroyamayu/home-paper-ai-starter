"""作り物のプリント（PDF）を作る。学校・幼稚園・会社・人の名前はすべて架空。

  python3 samples/build.py

HTML を書き出して、Chrome（headless）で PDF にする。日本語のフォント（Noto Sans CJK JP など）が要る。
できた PDF は samples/ に置いてあるので、ふつうは作り直す必要はない。
"""
import datetime as dt
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")
WD = "月火水木金土日"

CSS = """
@page { size: A4; margin: 18mm 16mm; }
body { font-family: 'Noto Sans CJK JP', 'Noto Sans JP', sans-serif; font-size: 11pt; line-height: 1.7; color: #222; }
h1 { font-size: 20pt; text-align: center; margin: 4mm 0; letter-spacing: .2em; }
.meta { display: flex; justify-content: space-between; font-size: 10pt; border-bottom: 2px solid #333; padding-bottom: 2mm; }
.right { text-align: right; }
h2 { font-size: 13pt; border-left: 6px solid #555; padding-left: 3mm; margin: 6mm 0 2mm; }
table { border-collapse: collapse; width: 100%; font-size: 10pt; }
th, td { border: 1px solid #555; padding: 1.5mm 2mm; vertical-align: top; }
th { background: #eee; }
.sat { color: #1a4fb5; } .sun, .hol { color: #c0392b; }
.box { border: 1.5px dashed #555; padding: 3mm 4mm; margin: 4mm 0; }
.small { font-size: 9pt; color: #555; }
.cut { border-top: 1px dashed #777; margin-top: 8mm; padding-top: 3mm; }
"""


def page(title, body):
    return f"<!doctype html><html lang='ja'><head><meta charset='utf-8'><title>{title}</title><style>{CSS}</style></head><body>{body}</body></html>"


def d(m, day):
    x = dt.date(2026, m, day)
    return f"{m}月{day}日（{WD[x.weekday()]}）"


DOCS = {}

# 1. 学年だより（長女の学年。発行 11/6）
DOCS["01_学年だより_11月号"] = page("学年だより 11月号", f"""
<div class='meta'><span>みどり小学校 第2学年</span><span>2026年11月6日 発行</span></div>
<h1>学年だより　11月号</h1>
<p>朝晩の冷え込みが厳しくなってきました。2年生は、来週の校外学習を楽しみに、生活科の学習に取り組んでいます。</p>
<h2>11月の主な予定</h2>
<table>
<tr><th style='width:30%'>日にち</th><th>行事</th><th style='width:35%'>持ち物・お願い</th></tr>
<tr><td>{d(11,11)}</td><td>校外学習（市民の森公園）</td><td>お弁当・水筒・レジャーシート</td></tr>
<tr><td>{d(11,18)}</td><td>図工「キャップでつくろう」</td><td>ペットボトルのキャップ 10個ほど</td></tr>
<tr><td>{d(11,20)}</td><td>持久走大会（雨天時は 11月24日）</td><td>体操服・水筒</td></tr>
<tr><td>{d(11,25)}〜{d(11,27)}</td><td>個人面談（14:00〜16:30）</td><td>希望の時間を別紙で提出してください</td></tr>
</table>
<h2>ご家庭へのお願い</h2>
<ul>
<li>図工で使うペットボトルのキャップは、洗って乾かしてから持たせてください。</li>
<li>持久走大会に向けて、朝ごはんをしっかり食べて登校させてください。</li>
<li>個人面談の希望調査は、<b>11月13日（金）まで</b>に担任へ提出してください。</li>
</ul>
<p class='right'>第2学年担任一同</p>
""")

# 2. 校外学習のお知らせ（11/5）
DOCS["02_校外学習のお知らせ"] = page("校外学習のお知らせ", f"""
<div class='meta'><span>保護者の皆様</span><span>2026年11月5日</span></div>
<p class='right'>みどり小学校　第2学年</p>
<h1>校外学習のお知らせ</h1>
<p>生活科「秋をさがそう」の学習として、下記のとおり校外学習を行います。</p>
<div class='box'>
<p><b>日　時</b>　{d(11,11)}　8:45 学校出発　／　14:30 学校着（予定）</p>
<p><b>行き先</b>　市民の森公園（徒歩）</p>
<p><b>持ち物</b>　お弁当・水筒・レジャーシート・ハンカチ・ティッシュ・汚れてもよい服装</p>
<p><b>雨天時</b>　{d(11,12)}に延期します。延期の場合も、お弁当をご用意ください。</p>
</div>
<p class='small'>※ 当日の朝、雨天で延期するかどうかは、7:00 までに学校の連絡メールでお知らせします。</p>
""")

# 3. 11月の行事予定表（表）
rows = []
events = {3: "文化の日", 5: "クラブ活動", 11: "2年 校外学習", 13: "面談希望調査 締切", 16: "避難訓練",
          18: "6時間授業", 20: "持久走大会", 23: "勤労感謝の日", 24: "持久走大会 予備日",
          25: "個人面談（〜27日）・短縮日課", 30: "委員会活動"}
holidays = {3, 23}
for day in range(1, 31):
    x = dt.date(2026, 11, day)
    cls = "hol" if day in holidays or x.weekday() == 6 else ("sat" if x.weekday() == 5 else "")
    rows.append(f"<tr class='{cls}' style='line-height:1.15'><td style='width:12%;padding:.2mm 2mm'>{day}</td><td style='width:10%'>{WD[x.weekday()]}</td><td>{events.get(day, '')}</td></tr>")
DOCS["03_11月の行事予定"] = page("11月 行事予定", f"""<style>@page {{ margin: 10mm 16mm; }} h1 {{ margin: 2mm 0; }}</style>
<div class='meta'><span>みどり小学校</span><span>2026年10月30日</span></div>
<h1>11月　行事予定</h1>
<table style='font-size:9pt'><tr><th>日</th><th>曜</th><th>行事</th></tr>{''.join(rows)}</table>
<p class='small'>予定は変更になることがあります。変更のときは学校だよりでお知らせします。</p>
""")

# 4. 給食献立表（表）
menu = ["ごはん・さばのみそ煮・ごま和え・豆腐のみそ汁", "コッペパン・ミートボール・コーンサラダ・ミネストローネ",
        "カレーライス・海そうサラダ・りんご", "ごはん・鶏のからあげ・ひじき煮・すまし汁", "きつねうどん・かぼちゃの天ぷら・みかん"]
rows = []
i = 0
for day in range(1, 31):
    x = dt.date(2026, 11, day)
    if x.weekday() >= 5 or day in holidays:
        continue
    rows.append(f"<tr><td style='width:16%'>{day}日（{WD[x.weekday()]}）</td><td>{menu[i % len(menu)]}</td><td style='width:12%'>牛乳</td></tr>")
    i += 1
DOCS["04_11月の給食献立"] = page("11月 給食献立表", f"""
<div class='meta'><span>みどり小学校</span><span>2026年10月28日</span></div>
<h1>11月　給食献立表</h1>
<table><tr><th>日</th><th>献立</th><th>飲み物</th></tr>{''.join(rows)}</table>
<p class='small'>11月11日（水）の2年生は校外学習のため、給食はありません（お弁当）。</p>
""")

# 5. 幼稚園のえんだより（長男）
DOCS["05_えんだより_11月"] = page("えんだより 11月", f"""
<div class='meta'><span>ひかり幼稚園</span><span>2026年11月2日</span></div>
<h1>えんだより　11月</h1>
<p>落ち葉がきれいな季節になりました。年長組は、どんぐりや落ち葉を使った製作を楽しんでいます。</p>
<h2>11月の予定</h2>
<table>
<tr><th style='width:30%'>日にち</th><th>行事</th><th style='width:35%'>持ち物</th></tr>
<tr><td>{d(11,11)}</td><td>お弁当の日</td><td>お弁当・フォーク</td></tr>
<tr><td>{d(11,17)}</td><td>いもほり（年中・年長）</td><td>軍手・着替え・ビニール袋</td></tr>
<tr><td>{d(11,26)}</td><td>おたんじょうかい</td><td></td></tr>
</table>
<p>寒くなってきましたので、上着には名前を書いてください。</p>
""")

# 6. 家電の取扱説明書（抜粋）
DOCS["06_食器洗い乾燥機_取扱説明書"] = page("取扱説明書", """
<div class='meta'><span>ミライ電機株式会社</span><span>形名 MD-500</span></div>
<h1>食器洗い乾燥機　取扱説明書（抜粋）</h1>
<h2>お手入れ：残さいフィルターの掃除</h2>
<ol>
<li>電源を切り、庫内が冷めていることを確かめます。</li>
<li>下かごを手前に引き出し、残さいフィルターを左に回して取り外します。</li>
<li>フィルターの汚れを、やわらかいブラシで水洗いします。</li>
<li>取り付けるときは、右に「カチッ」と音がするまで回します。</li>
</ol>
<p><b>目安：週に1回</b>。汚れがたまると、洗浄力が落ちたり、においの原因になったりします。</p>
<h2>こんなときは</h2>
<table>
<tr><th style='width:35%'>表示</th><th>原因と対処</th></tr>
<tr><td>E1 が点滅する</td><td>給水できていません。給水栓が開いているか確かめてください。</td></tr>
<tr><td>E4 が点滅する</td><td>排水できていません。残さいフィルターを掃除してください。</td></tr>
</table>
<p class='small'>お問い合わせ：ミライ電機 お客様相談室（架空の会社です）</p>
""")

# 7. 保証書
DOCS["07_食器洗い乾燥機_保証書"] = page("保証書", """
<h1>保証書</h1>
<table>
<tr><th style='width:30%'>品名</th><td>食器洗い乾燥機</td></tr>
<tr><th>形名</th><td>MD-500</td></tr>
<tr><th>保証期間</th><td>お買い上げ日から本体 1年間</td></tr>
<tr><th>お買い上げ日</th><td>2025年4月20日</td></tr>
<tr><th>販売店</th><td>あおば電器 駅前店（架空の店です）</td></tr>
</table>
<p>保証期間内に、取扱説明書に従った正常な使用状態で故障した場合は、無料で修理いたします。</p>
<p class='right'>ミライ電機株式会社</p>
""")


# 8. 算数のテスト（答案。赤ペンの丸付き。10 問中 2 問まちがい）
PROBLEMS = [("63", "28", "35", True), ("81", "45", "36", True), ("52", "27", "35", False),
            ("94", "56", "38", True), ("40", "13", "27", True), ("70", "34", "44", False),
            ("65", "19", "46", True), ("83", "48", "35", True), ("56", "29", "27", True),
            ("91", "64", "27", True)]
cells = []
for i, (a, b, ans, ok) in enumerate(PROBLEMS, 1):
    mark = ("<div class='ok'></div>" if ok else "<div class='ng'>✓</div>")
    cells.append(f"""<td><div class='no'>({i})</div><div class='hissan'>
<div>&nbsp;{a}</div><div>−{b}</div><div class='bar'></div><div class='ans'>&nbsp;{ans}</div>{mark}</div></td>""")
rows = "".join("<tr>" + "".join(cells[r * 5:(r + 1) * 5]) + "</tr>" for r in range(2))
DOCS["08_算数テスト_ひき算のひっ算"] = page("算数テスト", f"""<style>
.hissan {{ position: relative; font-family: 'Noto Sans Mono CJK JP', monospace; font-size: 20pt; line-height: 1.25;
          width: 26mm; margin: 2mm auto 4mm; text-align: right; }}
.bar {{ border-top: 2px solid #222; margin: 1mm 0; }}
.ans {{ font-family: 'Noto Serif CJK JP', serif; color: #3a3a3a; transform: rotate(-3deg); }}
.ok {{ position: absolute; right: -2mm; bottom: -2mm; width: 16mm; height: 11mm; border: 2.5px solid #d22;
       border-radius: 50%; transform: rotate(-8deg); }}
.ng {{ position: absolute; right: -6mm; bottom: 0; color: #d22; font-size: 26pt; transform: rotate(10deg); }}
.no {{ font-size: 11pt; }}
td {{ border: 1px solid #999; width: 20%; }}
.score {{ position: absolute; right: 0mm; top: 15mm; color: #d22; font-size: 30pt; font-family: 'Noto Serif CJK JP', serif;
          border: 3px solid #d22; border-radius: 50%; width: 32mm; height: 24mm; text-align: center; line-height: 24mm;
          transform: rotate(-6deg); }}
</style>
<div class='score'>80</div>
<div class='meta'><span>みどり小学校　2年1組</span><span>なまえ（　すずき　さくら　）</span></div>
<h1>ひき算の ひっ算</h1>
<p>つぎの けいさんを ひっ算で しましょう。（1もん 10てん）</p>
<table>{rows}</table>
<p class='small'>くり下がりに 気を つけよう。</p>
""")


def chrome():
    for c in ("google-chrome", "chromium", "chromium-browser"):
        if shutil.which(c):
            return c
    sys.exit("Chrome（または Chromium）が見つかりません")


def main():
    os.makedirs(SRC, exist_ok=True)
    exe = chrome()
    for name, html in DOCS.items():
        src = os.path.join(SRC, name + ".html")
        with open(src, "w", encoding="utf-8") as f:
            f.write(html)
        out = os.path.join(HERE, name + ".pdf")
        subprocess.run([exe, "--headless", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                        f"--print-to-pdf={out}", "file://" + src],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(out)
        scan(out, os.path.join(HERE, "scan", name + ".png"))


def scan(pdf, png):
    """スキャンしたような画像（1 ページ目・少し傾けて色を薄く）。OCR を試すとき用。赤ペンが読めるよう色は残す"""
    try:
        from PIL import Image, ImageFilter
    except ImportError:
        print("（Pillow が無いので、スキャン風の画像は作りません）")
        return
    os.makedirs(os.path.dirname(png), exist_ok=True)
    base = png[:-4]
    subprocess.run(["pdftoppm", "-r", "150", "-png", "-f", "1", "-l", "1", "-singlefile", pdf, base], check=True)
    im = Image.open(png).convert("RGB")
    im = im.rotate(0.8, resample=Image.BICUBIC, expand=True, fillcolor=(245, 245, 242))
    im = im.point(lambda v: min(255, int(v * 0.92 + 18))).filter(ImageFilter.GaussianBlur(0.4))
    im.save(png, optimize=True)
    print(png)


if __name__ == "__main__":
    main()
