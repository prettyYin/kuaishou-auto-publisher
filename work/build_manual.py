# -*- coding: utf-8 -*-
"""生成单文件图文使用说明（HTML，图片以 base64 内嵌，双击即可看）。"""
from __future__ import annotations

import base64
import pathlib

TOOL = pathlib.Path(r"C:\Users\Administrator\Documents\Codex\2026-09-16\w-x20\outputs\快手自动发布助手")
SHOTS = TOOL / "使用说明图片"


def img(name: str, caption: str, width: str = "920px") -> str:
    path = SHOTS / name
    if not path.exists():
        return "<p><i>（截图缺失：%s）</i></p>" % name
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return (
        '<figure><img src="data:image/png;base64,%s" style="max-width:%s;width:100%%;'
        'border:1px solid #ddd;border-radius:8px">'
        '<figcaption>%s</figcaption></figure>' % (data, width, caption)
    )


HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>快手自动发布助手 · 图文使用说明</title>
<style>
 body{font-family:"Microsoft YaHei UI","Microsoft YaHei",sans-serif;max-width:1000px;margin:0 auto;padding:24px 20px 60px;line-height:1.8;color:#232323;background:#fff}
 h1{font-size:27px;border-bottom:3px solid #ff5a5f;padding-bottom:12px;margin-top:8px}
 h2{font-size:20px;margin-top:40px;background:#fff5f5;border-left:6px solid #ff5a5f;padding:9px 14px;border-radius:4px}
 h3{font-size:16px;margin-top:24px;color:#0b5cad}
 code{background:#f3f4f6;padding:2px 6px;border-radius:4px;font-family:Consolas,monospace;font-size:13px}
 pre{background:#f7f8fa;border:1px solid #e6e8eb;border-radius:6px;padding:12px 14px;overflow:auto;font-size:13px;line-height:1.6}
 table{border-collapse:collapse;width:100%;margin:14px 0;font-size:14.5px}
 th,td{border:1px solid #e3e6e9;padding:9px 11px;text-align:left;vertical-align:top}
 th{background:#fafbfc;font-weight:600}
 tr:nth-child(even) td{background:#fcfdfe}
 figure{margin:18px 0}
 figcaption{color:#666;font-size:13px;margin-top:7px;text-align:center}
 .tip{background:#f0f7ff;border-left:5px solid #2f80ed;padding:11px 15px;margin:16px 0;border-radius:5px}
 .warn{background:#fff8e6;border-left:5px solid #f2a93b;padding:11px 15px;margin:16px 0;border-radius:5px}
 .danger{background:#fff1f0;border-left:5px solid #e5484d;padding:11px 15px;margin:16px 0;border-radius:5px}
 .lead{font-size:15.5px}
 .foot{color:#999;font-size:13px;margin-top:50px;text-align:center}
 ol,ul{padding-left:24px}
 li{margin:4px 0}
</style></head><body>

<h1>快手自动发布助手 · 图文使用说明</h1>
<p class="lead">这个工具帮你把「一条一条上传视频、改标题、再去金牛改素材名」的重复劳动自动化。</p>
<p class="lead">每天你只需要三步：<b>放视频 → 粘广告语 → 点开始</b>，剩下的它自己做完。</p>

<h2>一、它做什么 / 不做什么</h2>
<table>
 <tr><th style="width:50%">它替你做</th><th>它不会做</th></tr>
 <tr><td>在快手创作者服务平台按顺序<b>逐条上传视频</b></td><td>新建投放计划</td></tr>
 <tr><td>把作品标题填成<b>对应的广告语</b>并点发布</td><td>选素材投放、设置出价</td></tr>
 <tr><td>每条发布成功后<b>等 15 秒</b>再做下一条（保证顺序）</td><td>删除作品、修改作品可见性</td></tr>
 <tr><td>到磁力金牛把当天素材的<b>素材名改回视频文件名</b>（方便统计业绩）</td><td>帮你写广告语</td></tr>
</table>

<h2>二、第一次使用（只做一次，约 5 分钟）</h2>

<h3>第 0 步：解压并启动</h3>
<ol>
 <li>把 <code>快手自动发布助手-免安装版.zip</code> 解压到任意位置（建议放 <b>D 盘</b>，例如 <code>D:\\快手助手</code>，路径不要太深）；</li>
 <li>双击 <b>启动工具.exe</b>（推荐，不会出现命令提示符窗口）；</li>
 <li>随后出现客户端界面（首次启动约 5~10 秒）。</li>
</ol>
<div class="tip">双击 exe 没反应？先看任务栏是不是已经有窗口；确实没有，可以双击 <code>启动工具（无窗口）.vbs</code> 作为备用入口。需要看启动过程时再双击 <code>启动工具-显示日志.bat</code>。</div>

<h3>第 1 步：按「引导设置」填三步</h3>
<p>第一次打开会自动弹出引导设置；如果关掉了，点界面右上角的 <b>「引导设置」</b> 可以重新打开。</p>
""" + img("03-引导设置.png", "图 1：引导设置第 1 步——加账号、选浏览器和登录方式") + """
<ol>
 <li><b>账号、浏览器和登录方式</b>（打 <b>*</b> 的是必填）
   <ul>
    <li><b>账号名 *</b>：必填，自己看的名字（会出现在报表里），例如"A号-睫毛膏"；</li>
    <li><b>浏览器</b>：选你平时登录这些账号用的浏览器（Chrome / Edge 等，工具会自动列出本机已安装的）；</li>
    <li><b>登录方式</b>：<code>新建：首次扫码登录（推荐）</code> —— 不动你现有的浏览器，新开一个干净窗口扫码一次；<code>复用：某个已有配置</code> —— 复制你已登录的浏览器配置，免登录。</li>
    <li><b>金牛账户ID *</b>：必填。在浏览器里打开<b>该账号的磁力金牛「视频库」</b>，
      地址栏里 <code>__accountId__=</code> 后面那串数字就是（例如 <code>12345678</code>）。
      <br>实在找不到时，可以先在设置页点「打开浏览器检查登录」并切到金牛素材库，工具会自动识别并填回这个框。</li>
   </ul>
 </li>
 <li><b>两个平台网址</b>
   <ul>
    <li><b>创作者平台发布页</b>：浏览器里打开「发布作品」页面，复制地址栏；</li>
    <li><b>磁力金牛视频库</b>：打开「视频库 / 素材库」页面，复制地址栏。</li>
   </ul>
   <div class="warn">金牛地址要填<b>公共地址</b>（<code>https://niu.e.kuaishou.com/material/supervideo</code> 这一段），
   <b>不要带 <code>__accountId__=xxxx</code></b>——每个账号的账户 ID 在第 1 步各自填（必填）。</div>
 </li>
 <li><b>每个账号的素材文件夹</b>：点「选择文件夹」指定该账号<b>当天放视频的目录</b>；勾了「要用」的账号必须填。</li>
</ol>
<p>设置页全貌（账号增删、浏览器、登录方式、金牛账户ID、素材文件夹都在这里改）：</p>
""" + img("04-设置页.png", "图 2：设置页——每个账号一行，可随时增删账号") + """

<h3>第 2 步：每个账号登录一次</h3>
<p>进入 <b>「设置」</b> 页签 → 「浏览器窗口」区域：</p>
<ol>
 <li>「对哪个账号操作」选一个账号；</li>
 <li>点 <b>「打开浏览器检查登录」</b>（按钮会变灰几秒，状态栏会显示"正在等待浏览器就绪…"，属于正常）；</li>
 <li>窗口里如果要求登录，<b>扫码登录一次</b>，之后长期有效；</li>
 <li>每个账号重复一次。</li>
</ol>

<h3>第 3 步：先演练一遍</h3>
<p>回到 <b>「今天要发的」</b> 页签，点 <b>「仅演练（不发布）」</b>——它只走到"填好标题"就停，<b>不会真的发布</b>。
演练通过后再点「开始上传发布」。</p>

<h2>三、必填项清单（缺一个都跑不起来）</h2>
<table>
 <tr><th style="width:36%">位置</th><th style="width:26%">必填内容</th><th>怎么填</th></tr>
 <tr><td>引导设置第 1 步 / 设置 → 账号</td><td><b>账号名</b>（必填）</td><td>自己起的名字（不能留空，否则无法点「完成」）</td></tr>
 <tr><td>设置 → 账号</td><td><b>素材文件夹</b></td><td>当天视频所在目录（勾了「要用」的必须填）</td></tr>
 <tr><td>引导设置第 1 步 / 设置 → 账号</td><td><b>金牛账户ID</b>（必填）</td><td>金牛素材库地址里 <code>__accountId__=</code> 后面那串数字；留空时点「完成」会被拦下并提示怎么找</td></tr>
 <tr><td>设置 → 平台地址</td><td><b>创作者平台发布页网址</b></td><td>发布作品页的地址栏</td></tr>
 <tr><td>设置 → 平台地址</td><td><b>磁力金牛视频库（公共地址）</b></td><td>不带 <code>__accountId__</code> 的公共地址</td></tr>
 <tr><td>设置 → 浏览器窗口</td><td><b>每个账号扫码登录一次</b></td><td>点「打开浏览器检查登录」完成</td></tr>
 <tr><td>今天要发的</td><td><b>广告语</b></td><td>这一批视频共用的那一条；<b>必须独一无二</b>（不能和同事重复），否则改名可能改到别人的素材</td></tr>
</table>

<h2>四、每天怎么用（三步）</h2>
""" + img("01-主界面.png", "图 3：主界面——绿色＝已配对可以开跑；橙色/红色＝还缺东西") + """
<ol>
 <li><b>放视频</b>：把当天要发的视频放进各账号的素材文件夹。<br>
   顺序 = <b>文件名排序</b>（和你在资源管理器里看到的顺序一致）；</li>
 <li><b>粘广告语</b>：在对应账号行点 <b>「粘贴广告语」</b> → 先在表格/文档里选中广告语按 <code>Ctrl+C</code> → 在弹窗里点「从剪贴板粘贴」；</li>
 <li><b>点开始</b>：右侧「本次每账号最多处理」填好（填 <code>0</code> 或 <code>100</code> 表示不限）→ 点 <b>「开始上传发布」</b>。</li>
</ol>
""" + img("02-粘贴广告语.png", "图 4：设置广告语弹窗——这一批视频共用同一条广告语，并提醒广告语必须唯一") + """
<div class="danger"><b>广告语必须独一无二！</b><br>
改素材名时，工具是拿这条广告语去磁力金牛里<b>搜索素材</b>的。如果和同事用了同一句（或很像的）广告语，
就可能把别人上传的素材改名。所以：<b>一句广告语只给这一批视频用</b>，不要和别人重复。</div>

<h3>多个账号同时跑</h3>
<p>主界面有 <b>「并行执行已勾选账号」</b> 按钮，旁边可以设置 <b>同时最多 N 个账号</b>（默认 2，范围 1-5）。</p>
<table>
 <tr><th style="width:28%">行为</th><th>说明</th></tr>
 <tr><td><b>账号之间并行</b></td><td>多个账号同时运行；每个账号内部仍然逐条上传、逐条发布，顺序不会乱。</td></tr>
 <tr><td><b>发布完即可改名</b></td><td>某个账号发布结束后，立即开始自己的金牛改名，不等待其他账号。</td></tr>
 <tr><td><b>单账号停止</b></td><td>某账号失败或点「停止该账号」只停该账号；顶部按钮停止全部。</td></tr>
 <tr><td><b>并行安全预检</b></td><td>账号共用浏览器目录、调试端口、登录配置或金牛账户ID时，禁止并行并提示。</td></tr>
</table>
<p>并行会共用同一条网络和同一个 IP，可能让上传变慢或增加平台风控压力；不稳定时把并发数降到 1，或改用普通串行按钮。</p>
<h3>设置页和主界面的分工</h3>
<ul>
 <li><b>设置页</b>：账号名、浏览器、登录方式、金牛账户ID。</li>
 <li><b>今天要发的</b>：每天勾选「今天要发这个账号」、选择素材文件夹、粘贴广告语。</li>
 <li>设置页不再重复显示启用和素材文件夹；主界面账号名为只读显示。</li>
</ul>
<h3>作者声明和定时发布</h3>
<p>账号卡片里的 <b>「查看对照表」</b> 现在升级成“左边看顺序、右边改设置”：</p>
<table>
 <tr><th style="width:24%">设置项</th><th>怎么用</th></tr>
 <tr><td><b>作者声明</b></td><td>逐条选择，默认 <b>不设置</b>。选项与创作者平台一致：内容为AI生成、演绎情节仅供娱乐、个人观点仅供参考、素材来源于网络。选不上会重试 2 次，仍失败就跳过这一条并记录，不会带着错误声明发布。</td></tr>
 <tr><td><b>发布时间</b></td><td>逐条选择“立即发布”或“定时发布”。平台规则是只支持未来 1 小时到 14 天内；工具默认设置为当前时间 61 分钟后，避开边界。只要账号里有定时发布，本次就不会自动执行金牛改名，工具会把待改素材写进台账，下次打开时提醒你手动点「只改金牛素材名」。</td></tr>
 <tr><td><b>更多设置</b></td><td>预留了关联热点、添加地点、作者服务的分组位置，后续接入时不会增加左侧表格列数。</td></tr>
</table>
<div class="warn">作者声明只在本次打开工具期间有效；如果中途重开，未发布视频会按空声明继续。定时时间会保存在当天进度里。</div>
<ul>
 <li>本工具统一按「<b>这一批视频共用同一条广告语</b>」运行：弹窗里只填一条，保存时会再确认一次；</li>
 <li>粘贴的内容如果有多行，工具<b>只取第一行</b>并提示你；</li>
 <li>主界面上账号下面显示「已配对：N 个视频 · 全部使用同一条广告语」，看到这句才说明设置好了；</li>
 <li>想先看顺序对不对，点「查看对照表」，会列出「序号 / 文件名 / 广告语」。</li>
</ul>

<h2>五、界面按钮说明</h2>
<table>
 <tr><th style="width:32%">按钮</th><th>作用</th></tr>
 <tr><td><b>仅演练（不发布）</b></td><td>走完整流程但不点发布，用来验证顺序和广告语是否配对</td></tr>
 <tr><td><b>开始上传发布</b></td><td>真实上传并发布（作品会公开），跑完自动去金牛改名</td></tr>
 <tr><td><b>只改金牛素材名</b></td><td>只做改名这一步（不发布），适合补改留下的素材名</td></tr>
 <tr><td><b>停止</b></td><td>立刻中断当前操作并关闭自动化浏览器窗口</td></tr>
 <tr><td><b>上传前确认对照表</b></td><td>默认开：每个账号开始前弹一次对照表让你核对；关掉则静默执行</td></tr>
 <tr><td><b>改名前确认对照表</b></td><td>默认关：打开后会在金牛改名前列出对应关系</td></tr>
 <tr><td><b>上传发布完成后自动改名</b></td><td>默认开：发布完自动去金牛把素材名改回文件名</td></tr>
 <tr><td><b>今日进度</b></td><td>看当天每条视频的状态（含文件名与完整路径），可一键清空当天记录</td></tr>
 <tr><td><b>重置今日进度</b></td><td>清空当天记录，让所有视频重新发布一遍</td></tr>
</table>

<h2>六、注意事项（重要）</h2>
<div class="danger">1. <b>作品是公开发布的</b>。发布前请核对对照表（默认会弹），确认「文件名 ↔ 广告语」一一对应。</div>
<ol>
 <li><b>广告语必须唯一</b>：改名是靠"搜索这条广告语"找到素材的，和同事重复就可能改到别人的素材。</li>
 <li><b>一次只点一次开始</b>。运行时按钮会置灰；要停就点「停止」，不要重复点击，也不要同时开第二个窗口（程序会阻止第二个实例并提示你）。</li>
 <li><b>运行期间不要关机</b>（工具会自动阻止电脑休眠），也不要关闭自动化浏览器窗口；建议晚上开跑、早上看报表。</li>
 <li><b>速度预期</b>：单条视频几百 MB 时上传较慢，而且是"一条一条来、每条发布后等 15 秒"，跑完一批可能要几小时。</li>
 <li><b>不要手动去翻自动化浏览器窗口里的页面</b>（除了登录、验证码）。脚本要停在特定页面才能工作。</li>
 <li><b>验证码 / 掉登录</b>：脚本会停下并提示你，手动处理后重新点开始，会<b>从断点继续，不会重复发布</b>。</li>
 <li><b>素材名要等于视频文件名</b>：脚本是把文件夹里的文件名照搬过去，所以请保证视频文件名本身规范（例如 <code>9.16-某人-日期.mp4</code>）。</li>
 <li>若素材数量对不上（常见于同事先传过、或还在审核），脚本<b>不再弹窗打断</b>：它会按实际查到的条数继续改名（用视频时长逐条核对），剩下的保持原名并在日志里写明。</li>
 <li>改名时脚本按<b>视频时长</b>把素材和文件夹里的视频配对（容差 ±1 秒）；
   如果多条素材时长相同（或读不到时长），再按<b>"上传先后 ↔ 文件夹顺序"</b>依次配对（文件夹里靠前的对应上传较早的）；
   仍配不上的会<b>保持原名</b>并在报表里标为"待核对"。</li>
</ol>

<h2>七、出问题怎么办</h2>
""" + img("05-使用帮助.png", "图 5：使用帮助页签——一键复制诊断信息") + """
<ol>
 <li>点「使用帮助」页签 → <b>「复制诊断信息」</b> → 粘贴发给管理员（里面只有配置和日志，没有密码）；</li>
 <li>需要更细的排查，用 <code>启动工具-显示日志.bat</code> 启动，能实时看到每一步；</li>
 <li>日志与出错截图位置：工具目录下的 <code>logs\\</code>（<code>logs\\shots\\</code> 是出错时的页面截图）。</li>
</ol>
<table>
 <tr><th style="width:42%">现象</th><th>处理办法</th></tr>
 <tr><td>提示"有视频被记录为今天已发布"，但它其实没发出去</td><td>选「全部重新发布一遍」清掉错误记录重发；或到「今日进度」里清空当天记录</td></tr>
 <tr><td>日志显示"查询到的素材条数和文件夹视频数不一致"</td><td>多为素材还在审核或同事已传过。脚本会<b>自动按查到的条数继续改名</b>（用视频时长逐条核对），剩余保持原名，不需要你操作</td></tr>
 <tr><td>点了「只改金牛素材名」后好像没反应</td><td>先看状态栏是否在显示"等待…/查询…"（日志里会有"开始查询「…」"）；如果浏览器窗口停在别的页面，脚本会自己切回金牛素材库。<b>不会再弹窗等你确认</b></td></tr>
 <tr><td>金牛里有素材名没改成功</td><td>看日志里的"待核对"；先到「设置 → 清理残留窗口」，再单独跑一次「只改金牛素材名」</td></tr>
 <tr><td>提示"读不到素材时长"、一条都没配上</td><td>通常是金牛列表里的<b>「视频时长」列被隐藏</b>了。工具会自动打开这一列；若仍不行，请在金牛点工具栏的「自定义列表」把「视频时长」勾上、确定，再重跑</td></tr>
 <tr><td>浏览器窗口开着、按钮点不动</td><td>「设置 → 清理残留窗口」，或手动关闭那个自动化浏览器窗口</td></tr>
 <tr><td>双击没反应 / 界面打不开</td><td>看任务栏是否已有窗口；再试 <code>启动工具-显示日志.bat</code>，把报错内容发管理员</td></tr>
 <tr><td>点了开始后"好像卡住"、主界面点不动</td><td>先看客户端是否有弹窗被浏览器挡住（现在所有弹窗都会自动<b>置顶显示</b>）；「本次运行结束」的结果窗口<b>不会锁住主界面</b>，可以直接关掉。若在等某个操作，点「停止」会立刻中断</td></tr>
 <tr><td>登录失效</td><td>在自动化浏览器窗口扫码登录，然后重新点开始（会从断点继续）</td></tr>
</table>

<h2>八、每天跑完看什么</h2>
<table>
 <tr><th style="width:30%">内容</th><th>位置</th></tr>
 <tr><td><b>结果报表</b></td><td>工具目录 <code>报表\\运行结果_日期.xlsx</code>（每条视频的发布状态、作品链接、素材名修改状态、耗时）</td></tr>
 <tr><td><b>当天明细</b></td><td>客户端右上角「今日进度」</td></tr>
 <tr><td><b>运行日志</b></td><td>工具目录 <code>logs\\</code></td></tr>
 <tr><td><b>启动日志</b></td><td>工具目录 <code>启动日志.txt</code>（排错时最先看这个）</td></tr>
</table>

<h2>九、分享给同事（把配置搬过去）</h2>
<ol>
 <li>你这边：<b>设置页 → 「导出配置给同事」</b> → 保存出一个 json 文件（含账号名单、两个平台网址、节奏设置、页面规则，<b>不含</b>本机浏览器路径）；</li>
 <li>同事那边：解压工具 → <b>设置页 → 「导入同事的配置」</b> → 选中你给的 json；</li>
 <li>同事再为每个账号点一次「打开浏览器检查登录」扫码（登录态不能复制，各机器各登一次）；</li>
 <li>同事的素材文件夹路径与你的不同，需要在设置页改成他自己的目录。</li>
</ol>

<h2>十、目录结构</h2>
<pre>快手自动发布助手-免安装版/
├─ 启动工具.bat              ← 每天双击这个（无黑窗口）
├─ 启动工具-显示日志.bat      ← 排查问题时用（保留日志窗口）
├─ 使用说明.html（本文档）    ← 双击用浏览器打开，图文都在里面
├─ python/                   ← 自带运行环境（不要删、不要改）
├─ app/                      ← 程序本体
├─ config/
│   ├─ config.json           ← 账号、网址、节奏（界面上改更方便）
│   └─ selectors.json        ← 后台页面规则（由管理员维护）
├─ logs/                     ← 运行日志、出错截图
├─ runs/                     ← 当天进度与广告语（断点续跑用）
├─ 报表/                     ← 每天生成的结果表
└─ 启动日志.txt              ← 每次启动的记录</pre>
<p>整个文件夹可以整体拷到别的电脑使用（对方电脑需要装有 Chrome 或 Edge 浏览器）。</p>

<h2>十一、常见概念速查</h2>
<ul>
 <li><b>对照表</b>：`序号 / 文件名 / 广告语` 的对应清单，发布前核对用；</li>
 <li><b>演练模式</b>：不点发布的完整走查；</li>
 <li><b>断点续跑</b>：已发布成功的条目会记下来，重开工具会跳过，不会重复发布；</li>
 <li><b>金牛账户ID</b>：磁力金牛里每个投放账号的编号（素材库地址里的 <code>__accountId__=</code>）；</li>
 <li><b>素材名</b>：磁力金牛里那条素材显示的名字，本工具会把它改成<b>视频文件名</b>。</li>
</ul>

<p class="foot">快手自动发布助手 · 本说明随工具一起分发（图片已嵌入本文档，无需其他文件）</p>
</body></html>
"""


def main() -> None:
    target = TOOL / "使用说明.html"
    target.write_text(HTML, encoding="utf-8")
    print("已生成：%s（%.0f KB）" % (target, target.stat().st_size / 1024))


if __name__ == "__main__":
    main()
