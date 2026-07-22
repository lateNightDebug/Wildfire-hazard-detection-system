品牌化文件夹 (Branding)
========================

把品牌素材放进这个文件夹,重启应用即可生效 —— 不用改代码。

1) LOGO
   放一个文件命名为 logo.png / logo.svg / logo.jpg 之一。
   导航栏左上角会自动显示它(高度 32px,宽度自适应)。
   没有 logo 文件时,只显示文字标题。

2) 名称和副标题 + 颜色
   编辑 brand.json:
   - "app_name"  : 导航栏主标题(如 "CIRUS Wildfire Detection")
   - "subtitle"  : 副标题(如 "Operations Console")
   - "colors.primary"       : 主题主色(深色,导航高亮/按钮),十六进制如 "#1B4079"
   - "colors.primary_light" : 主题浅色(状态点/进度),十六进制

3) 生效
   改完后重启桌面应用(关窗口重开)。界面会读取本文件夹的最新内容。

注意: 这个文件夹是本地品牌配置,不会进 Git(已 gitignore),
所以每台机器可以有自己的品牌设置,更新代码也不会覆盖你的 logo。
