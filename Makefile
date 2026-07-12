# Repo-level shortcuts. `make test` runs the backend suite.
.PHONY: test test-backend

## test: run all test suites
test: test-backend

## test-backend: run the FastAPI backend pytest suite
test-backend:
	$(MAKE) -C backend test
