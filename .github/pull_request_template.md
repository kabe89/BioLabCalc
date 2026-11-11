## Description
Briefly describe the purpose of this pull request, the problem it solves, or the feature it introduces.

## Type of Change
Please check the options that apply:
- [ ] 🐛 Bug fix (non-breaking change fixing a calculation or logic error)
- [ ] 🧬 New scientific calculation / module (adds new wet-lab or bioinformatic feature)
- [ ] ⚡ Performance optimization or refactor
- [ ] 📝 Documentation update (README, docstrings, examples)
- [ ] 🧪 Tests (adds or updates unit tests)
- [ ] 🖥️ ELN / Web UI feature or fix

## Scientific & Mathematical Validation
If this PR introduces or alters a calculation or biochemical model:
- **Reference / Citation**: *(e.g., SantaLucia, J. (1998) PNAS 95(4):1460-1465, or NEB/ThermoFisher formulation guidelines)*
- **Mathematical Formula**: *(Brief explanation of the equations used)*
- **Units**: *(Explicitly verify all input and output units: e.g., µL, ng/µL, fmol, Da, °C)*

## Checklist
- [ ] My code follows the style guidelines of this project (PEP 8, type hints).
- [ ] I have added docstrings and inline comments explaining complex mathematical logic.
- [ ] I have added unit tests in `tests/` that verify the calculation against known benchmarks or literature controls.
- [ ] All tests pass locally (`$env:PYTHONPATH="src"; python -m unittest discover tests`).
- [ ] I have updated documentation or README if applicable.
- [ ] My changes generate no new warnings or unhandled exceptions.
