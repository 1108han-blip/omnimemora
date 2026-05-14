.PHONY: start start-runtime start-adapter health doctor doctor-json doctor-react data-governance

start:
	bash ./start.sh

start-runtime:
	cd 4_core/local-runtime && go build -o ../../tools/omnimemora-runtime . && ../../tools/omnimemora-runtime serve

start-adapter:
	PORT=18011 python tools/_run_adapter.py

health:
	curl -fsS http://127.0.0.1:8765/health
	curl -fsS http://127.0.0.1:18011/health

doctor:
	@python3 tools/doctor_quality.py

doctor-json:
	@python3 tools/doctor_quality.py --json

doctor-react:
	@python3 tools/doctor_quality.py --react-doctor

data-governance:
	powershell -ExecutionPolicy Bypass -File .\tools\verification\data_governance\run_all.ps1 -RunLabel "make" -Tenant all -Salt "replace-me"
