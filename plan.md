# iqlabs-python-sdk PyPI 배포 계획

## Context

`iqlabs-python-sdk`를 PyPI에 배포하여 `pip install iqlabs-solana-sdk`로 설치 가능하게 만든다.
배포 전 JS SDK (`iqlabs-solana-sdk`)와의 상수 불일치를 수정하고, IDL 패키징 문제를 해결해야 함.

---

## 0단계: JS SDK와 상수 불일치 수정 (Critical)

JS SDK와 비교 결과 3가지 심각한 불일치 발견. 배포 전 반드시 수정 필요.

**`iqlabs/contract/constants.py`:**
- `DEFAULT_ANCHOR_PROGRAM_ID`: `7dL1jKd4CaFHQRV2SU23XJtSCrPXaLpEbq9FteRXup8v` → `9KLLchQVJpGkw4jPuUmnvqESdR7mtNCYr3qS4iQLabs`
- `DEFAULT_PINOCCHIO_PROGRAM_ID`: `7dL1jKd4CaFHQRV2SU23XJtSCrPXaLpEbq9FteRXup8v` → `9KLLchQVJpGkw4jPuUmnvqESdR7mtNCYr3qS4iQLabs`

**`iqlabs/sdk/constants.py`:**
- `DIRECT_METADATA_MAX_BYTES`: `900` → `850`
- `DEFAULT_IQ_MINT`: `4mxHqXJfcydM6iDF4aFoG1R9YFxqiJ3B6HZBHjUxx7uX` → `3uXACfojUrya7VH51jVC1DCHq3uzK4A7g469Q954LABS`
- 누락된 `CHUNK_SIZE = 850` 상수 추가

일치 확인된 항목: 모든 seed 문자열, PDA 도출, instruction discriminator, `DEFAULT_WRITE_FEE_RECEIVER` ✅

---

## 1단계: IDL 파일을 패키지 내부로 이동

현재 `idl/code_in.json`이 패키지 밖에 있어 pip 설치 시 경로가 깨짐.

- `idl/code_in.json` → `iqlabs/idl/code_in.json`으로 복사
- `iqlabs/contract/instructions.py` line 12: `Path(__file__).parent.parent.parent / "idl"` → `Path(__file__).parent.parent / "idl"`
- `iqlabs/coder.py` line 14: `Path(__file__).parent.parent / "idl"` → `Path(__file__).parent / "idl"`

---

## 2단계: pyproject.toml 업데이트

```toml
[project]
name = "iqlabs-solana-sdk"
version = "0.1.0"
description = "IQLabs Solana SDK for Python — on-chain data storage, database tables, and connections"
readme = "README.md"
<!-- license = {text = "MIT"} --> 

/Users/sumin/WebstormProjects/iqlabs-solana-sdk 여기 라이선스 참고

requires-python = ">=3.10"

authors = [
    {name = "IQLabs", email = "dev@iqlabs.io"},
]
keywords = ["solana", "blockchain", "sdk", "iqlabs", "on-chain", "inscription"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Software Development :: Libraries",
]
dependencies = [
    "solana>=0.32.0",
    "solders>=0.21.0",
    "anchorpy>=0.19.0",
    "pycryptodome>=3.20.0",
]

[project.urls]
Homepage = "https://github.com/iqlabs-official/iqlabs-python-sdk"
Repository = "https://github.com/iqlabs-official/iqlabs-python-sdk"

[tool.setuptools.packages.find]
include = ["iqlabs*"]

[tool.setuptools.package-data]
iqlabs = ["idl/*.json"]
```

---

## 3단계: LICENSE 파일 생성 ()
/Users/sumin/WebstormProjects/iqlabs-solana-sdk 여기 라이선스 참고
---

## 4단계: 빌드 및 배포

```bash
pip install build twine
python -m build
twine upload dist/*
```

---

## 검증

1. `pip install iqlabs-solana-sdk` 성공 확인
2. `from iqlabs import writer, reader` import 확인
3. IDL 파일 경로가 정상적으로 로드되는지 확인
