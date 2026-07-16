# 交付计划(答辩周)

对照原始需求表整理,每完成一项打勾。规则:commit 不带 AI 署名。

## 本周必做

- [ ] **Commit 全部现有工作**(40+ 文件,无署名)
- [ ] **Scan Detail 显示无人机型号**(EXIF Make/Model),开发机 GPU 降级为 "Processed on" 一行
- [ ] **地图弹窗加照片缩略图**(Dashboard + Map 页)
- [ ] **PDF 汇总页加 GPS pin 地图**
- [ ] **Settings 补全**:报告输出路径设置(重启生效)+ 模型下载按钮
- [ ] **Alerts 加回 Coming Soon 占位**(按原计划)
- [ ] **通用设备支持核查**:去掉代码/文档里写死 RTX 4090 的假设(任意 CUDA GPU / Apple MPS / CPU)
- [ ] 全量测试保持绿色,收尾 commit

## 等待外部条件

- [ ] **接入训练好的 dead_tree.onnx**(模型还在 Azure 训练;放进 models/ + Settings 页调预处理开关)
- [ ] **MRK 文件 GPS 解析**(比 EXIF 准)——先确认无人机数据里有没有 .MRK(RTK 机型才有),有再做
- [ ] **真实 100–200 张航次全流程压测**(拿到真实数据后)

## 明确推迟(答辩讲成 roadmap,不做)

- [ ] 真卫星底图 + 道路分类 + 河流湖泊(Leaflet + Esri 离线瓦片,方案已调研)
- [ ] GPS 检测去重(站点聚类 → 几何投影 → ODM 正射拼图三层方案)
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
