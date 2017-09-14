test: 
	python -m pytest --doctest-modules --cov=fsmcontainers --cov-report html:cov_html 

dicttest:
	python -m pytest --cov=fsmcontainers --cov-report html:cov_html dicttests.py

settest:
	python -m pytest --cov=fsmcontainers --cov-report html:cov_html settests.py
