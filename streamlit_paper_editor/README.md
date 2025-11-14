
论文写作AI辅导平台 (Streamlit)
================================

说明
----
这是一个可运行的 Streamlit 项目模板，旨在对接两个微调过的 ChatGPT 模型：
1. `segment_model` - 将论文分为修辞段落，输出 key `segment_data`（见 Output Format）。
2. `error_model` - 识别论文中出现的错误代码（例如 A1, B1...），输出 `error_part` 和 可选 `instances`。

如何使用
--------
1. 在 `model_configs.json` 中填写你两个模型的 HTTP 接口地址（或代理地址）。
   - 推荐在系统环境变量中保存 API keys，并在 json 中填写 `api_key_env` 字段的变量名。
2. 在 `errors.json` 中可以编辑/添加错误代码与描述。默认包含 A1, B1, C1, D1, F2, I2。
3. 安装依赖并运行：
   ```
   pip install -r requirements.txt
   streamlit run app.py
   ```
   或使用 `run.sh`（类 Unix）。

功能要点
------
- 学生输入姓名/学号并上传论文（txt/pdf/docx）。
- 将论文发送到分段模型与错误检测模型（通过配置的 API）。
- 显示分段结果，显示错误检测结果（若模型返回实例位置则显示）。
- 点击某个实例开始编辑：计时器启动；提交后统计删除/插入/替换的词数，并尝试将修改应用回全文。
- 会话可导出为 zip，包含原始稿、本次稿、AI 分段结果、AI 错误检测结果、编辑日志、以及 AI 会话记录。

注意
----
- 该模板假设你的微调模型返回 JSON 并遵循约定的字段（见 app.py 内调用说明）。
- 本项目仅为模板：在真实部署到线上时请注意安全（不要在代码中写入明文 API keys）。
