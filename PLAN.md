# 交付计划(答辩周)

对照原始需求表整理,每完成一项打勾。规则:commit 不带 AI 署名。

## 本周必做

- [x] **Commit 全部现有工作**(40+ 文件,无署名)
- [x] **Scan Detail 显示无人机型号**(EXIF Make/Model,实测 DJI L2),开发机 GPU 降级为 "Processed on" 一行(旧 run 无此字段,显示 "not in EXIF";新 run 自动带)
- [x] **地图弹窗加照片缩略图**(Dashboard + Map 页)
- [x] **PDF 汇总页加 GPS pin 地图**(按检测类型着色,含图例)
- [x] **Settings 补全**:报告输出路径设置(重启生效)+ 模型下载按钮
- [x] **Alerts 加回 Coming Soon 占位**(按原计划)
- [x] **通用设备支持核查**:代码本就通用(任意 CUDA → Apple MPS → CPU),仅注释写死 4090,已改
- [x] 全量测试保持绿色(61 个),收尾 commit

## 第二批(2026-07-16 完成)

- [x] **MRK 文件 GPS 解析**:DJI RTK Timestamp.MRK(厘米级)优先于 EXIF(米级);照片序号自动匹配;真实 DJI L2 数据验证通过。MRK 需和照片放在同一文件夹(任务文件夹原样导入即可)
- [x] **图片预压缩(老师方案)**:超过 `preprocess_max_mb`(默认 2MB)的图在检测前重编码(保分辨率、质量阶梯),Settings 页可调,0 关闭
- [x] **真卫星底图(Leaflet + Esri 离线瓦片)**:`scripts/fetch_map_tiles.py --bbox ... --zoom 11 15` 出发前抓一次,Map 页自动切换真卫星图(可缩放/拖动);无瓦片自动回退风格化底图。已抓好 Canmore 作业区 480 张瓦片
- [x] **道路分类 + 河流湖泊**:`scripts/fetch_map_overlays.py` 从 OSM 抓 GeoJSON(主干道/小径分级、河流、湖泊),离线渲染在卫星图上。作业区已抓 2880 条要素
- [x] **GPS 检测去重·第 1 层(站点聚类)**:全部带检测图片按 ≤40m 聚成"站点",地图按站点打标(计数徽章 + 最高严重度 + 成员图片列表),页面明示"N 张图合并为 M 个站点"

## 第三批·真机反馈修复(2026-07-16 完成)

- [x] **Leaflet 地图卡死修复**:根因 = 2880 条道路/水系用 SVG 渲染拖死 WebView2;切换 Canvas 渲染器(preferCanvas),实测 SVG path 归零、导航可正常离开地图页
- [x] **Dashboard 地图与 Map 同步**:两页共用同一份站点数据(/api/map-data)和同一 Leaflet 组件,有瓦片同时切真卫星图
- [x] **Scans 大数据量二次筛选**:按天折叠(最新天默认展开);超 250 张的连续大航次自动切 part 1/N(实测 1558 张 → 7 段);每段可 "Select images" 展开缩略图勾选后只检测选中的
- [x] **界面内下载区域地图**:Map 页无瓦片时出横幅按钮、Settings 页 Offline map 卡;bbox 自动取自所有 scan 的 GPS,后台下载带进度
- [x] **目录整洁**:map_tiles/ → **map/**(瓦片 + overlays.geojson 都在里面);models/ = 模型;outputs/ = 运行结果
- [x] **删除"水滴"logo**

## 第四批(2026-07-16 完成)

- [x] **详情页图片缩放**:滚轮缩放(指向光标位置,最高 12×)、拖拽平移、双击复位;复核画框模式下缩放照常可用
- [x] **地图标记改类型配色**:火=红、烟=橙、**枯树=黄**(与标注框一致),图例同步;弹窗同时保留严重度徽章
- [x] **打包分发**:`install.bat`(一键装环境+桌面快捷方式)+ `INSTALL.md`(打包=`git archive`,对方=装 Python→解压→双击 install.bat)

## 第五批(2026-07-16 完成)

- [x] **地图不再盖住导航栏**:导航 z-index 提到 Leaflet 之上 + 地图容器加 stacking context 隔离
- [x] **Severity Distribution 换成 Hazard Overview**:检测类型统计(类型配色横条)+ 复核积压(几个 run 待确认,一键跳 Review)+ 训练集规模(已确认框数)——三个都是"接下来该干什么"的信号
- [x] **选图器改全屏二级弹窗**:大缩略图(170px 网格)、文件名秒开、缩略图**逐张按需生成+懒加载**(不再一次性生成 100 张,卡顿根除)、Esc/点遮罩关闭

## 等待外部条件

- [ ] **接入训练好的 dead_tree.onnx**(模型还在 Azure 训练;放进 models/ + Settings 页调预处理开关)
- [ ] **真实 100–200 张航次全流程压测**(拿到真实数据后)

## 明确推迟(答辩讲成 roadmap,不做)

- [ ] GPS 去重第 2/3 层(几何投影 → ODM 正射拼图)
- [ ] 200 张报告瘦身 + GeoJSON 导出
- [ ] 流水线并行加速(换 ONNX 模型本身就是最大提速)
- [ ] Mac 实机验证(代码层面已兼容 MPS/CPU,未实测)
- [ ] Alerts 功能本体

## 已完成(存档)

- [x] Layer 1 检测(SAHI+YOLO 火/烟 + DeepForest 枯树提案)
- [x] Layer 1.5 人工复核 → labels.json 训练集(控制台内置画框编辑器)
- [x] Layer 2 报告(LM Studio 降级 + ReportLab PDF,时间戳命名永不覆盖)
- [x] ONNX 检测器插件(Custom Vision / YOLO 导出自适应,即插即用)
- [x] Custom Vision 训练集导出 + 上传脚本(tile 切分匹配推理分布)
- [x] 操作控制台六页:Dashboard / Scans / Review / Map / Reports / Settings
- [x] 任务文件夹导入(按天/航次分组,忽略遥测文件)
- [x] 显示级严重度(枯树密度驱动,阈值可配)
- [x] 输出分类存放(originals / annotated / gridmaps)
- [x] 桌面应用形态(pywebview 原生窗口 + 图标 + 快捷方式)
- [x] 59 个自动化测试
