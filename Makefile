test: 
	python -m pytest -x --cov=fsmcontainers --cov-report html:cov_html tests.py

dicttest:
	python -m pytest -x --cov=fsmcontainers --cov-report html:cov_html dicttests.py
