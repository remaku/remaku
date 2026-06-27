from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files("rapidocr_onnxruntime", includes=["**/*.onnx", "**/*.yaml"])
