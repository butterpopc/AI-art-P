# NovelAI 제작 경로

> 실행 전 [현재 상태](status.md)와 [완료 시험](experiments.md)을 확인합니다. 아래 V5 목표와 생성 명령은 과거 기록이며 비용 0이나 현재 모델 선택을 보장하지 않습니다. NovelAI 주력·ComfyUI 보조, 추가 Anlas 차감 0 조건을 우선합니다.

**현재 목표는 V5 Full이다.** 아래 생성 스크립트는 앞선 V4.5 시험을 재현하는 도구이며 V5 제작 준비가 완료되었다는 뜻이 아니다. V5 전환은 [조사 기록](v5-research.md)과 [제작 계획](production-plan.md)에 따른다. 기존 모델 이름만 바꿔 비용·기능 검증을 생략하지 않는다.

현재 저장소의 `seorin-*.png` 이미지는 Codex 이미지 도구로 만든 검토본이다. NovelAI 산출물이 아니다. 공식 API를 통한 계정 인증과 **활성 Opus(tier 3)** 구독 확인은 완료했다. NovelAI 이미지 생성 성공 여부와 개별 결과의 시각 검수는 산출물 메타데이터·검수 기록에서 따로 확인한다.

## 인증과 실행

Python 3.10 이상과 표준 라이브러리만 사용한다. 별도 패키지 설치가 필요 없다. `NOVELAI_API_TOKEN`은 보안 환경 설정으로 주입한다. 환경변수가 설정되어 있으면 항상 우선 사용한다. 또는 저장소 밖의 비공개 JSON 파일을 `--credentials-file`로 지정할 수 있다. 이 경우 `api_token` 문자열만 인증에 사용하며, 이메일·비밀번호는 사용하거나 출력하지 않는다. 파일은 소유자 전용 권한(600), 바로 위 디렉터리는 소유자 전용 권한(700)이어야 한다. 저장소 내부 파일과 그룹·타인에게 권한이 열린 파일/디렉터리는 거절한다. 토큰·비밀번호 값 자체를 명령행 인자, 소스, 프롬프트, 이미지 메타데이터에 넣지 않는다. 도구는 로그인·회원가입·구독 변경·구매를 수행하지 않는다.

저장소 루트 `/workspace/AI-art-P`에서 실행한다.

```sh
python tools/novelai.py --dry-run
python tools/novelai.py --check
python tools/novelai.py --generate --output artwork/novelai-seorin-001.png
```

이 환경의 비공개 인증 파일을 사용할 때는 다음처럼 **경로만** 전달한다. 이 파일은 공개 저장소·클라이언트 전달 ZIP에 포함하지 않는다.

```sh
python tools/novelai.py --check --credentials-file /workspace/private-ai-art-p/credentials.json
python tools/novelai.py --generate --credentials-file /workspace/private-ai-art-p/credentials.json --output artwork/novelai-seorin-next.png
```

`--dry-run`은 인증 없이 로컬 설정만 검증한다. `--check`는 `https://image.novelai.net/user/subscription`에서 활성 여부와 티어만 출력한다. 기존 `api.novelai.net` 경로는 이 계정 요청에 HTTP 400과 이미지 호스트로 이전하라는 안내를 반환하여 공식 이미지 API 호스트를 사용한다. `--generate`는 활성 Opus 티어를 확인한 뒤 **이미지 한 장**을 요청한다. API 응답은 JSON의 base64 PNG만 받아 지정한 파일에 기록한다. 원격 파일명이나 ZIP 경로는 사용하지 않는다. TLS 인증을 유지하고 리디렉션을 거절한다.

성공 시 같은 이름의 JSON 파일에 프롬프트, 모델, 시드, 크기, 생성 시각, SHA-256을 기록한다. 시드는 같은 조건의 비교에 유용하지만 서비스의 모델 변경까지 포함한 영구적인 동일 출력을 보장하지 않는다. 기존 결과물은 덮어쓰지 않는다.

## 비용과 반복 작업

공식 안내에 따라 V4.5 Full, 832×1216, 28 steps, 이미지 1장, 입력 이미지 없는 text-to-image를 기본값으로 둔다. Opus의 일반 크기 무료 생성 조건을 지키기 위한 설정이다. V5, 배치 생성, 이미지 참조·img2img, 업스케일 등 별도 비용이 발생할 수 있는 기능은 이 도구에서 거절한다. 구매 API는 전혀 사용하지 않는다. 활성 Opus 상태는 실제 응답으로 확인했으며, 생성할 때마다 다시 확인한다. 서비스 요금 정책과 실제 과금은 서버가 결정하므로 생성 결과와 잔액 확인을 별도로 기록한다.

요청 실패나 시간 초과 뒤 자동 재시도하지 않는다. 시간 초과 때 서버에서는 이미 생성되었을 수 있으므로, 결과를 확인하고 원인을 판단한 후 다음 요청을 별도로 실행한다. 무인 반복이나 대량 요청 루프를 두지 않는다. 사용자의 제작 요청에 따라 시안을 한 장씩 만들고, 시각 검수 후 다음 프롬프트를 조정한다.

`prompts/novelai-seorin-v1.json`은 서린의 외형을 전달하는 출발점이다. 원본 참고 이미지의 직접 재현을 검증한 프롬프트가 아니다. 얼굴·머리핀 방향·치마 앞뒤·손·발·표정 일관성을 실제 결과에서 확인한다. 클라이언트 승인 여부는 항상 별도로 기록한다.

## 검증 범위

실제로 V4.5 text-to-image 001과 Precise Reference 002를 생성했다. 둘 다 구조·작화 검수에서 전달본으로 선택하지 않았다. `tools/novelai_reference.py`는 별도 단일 참조 호출 도구로, 구독 Anlas 전후 차감과 150-Anlas 초기 시험 한도를 기록한다. 002의 실제 참조 비용은 5 Anlas였다. 이미지·지시문·메타데이터는 기록하되 입력 이미지의 base64와 인증 정보는 메타데이터에 복사하지 않는다. 이 참조 경로는 V5 지원으로 간주하지 않는다.

```sh
python -m unittest discover -s tests -p 'test_novelai.py' -v
```

로컬 검증은 유효한 설정, 미인증·비활성 구독 차단, 유료 기능 차단, 비밀값 비기록, 오류 시 재전송 방지, PNG 크기 확인, 원격 경로 무시, 덮어쓰기 방지, 리디렉션 차단, 비공개 인증 파일 권한·위치 검사 및 환경변수 우선 사용을 다룬다. 모의 테스트는 실제 연결 테스트와 구분한다. 실제 계정 인증·활성 Opus 확인은 별도로 완료했다.

## 공식 참고 자료

- 이미지 API: https://image.novelai.net/docs/index.html
- 계정 API: https://api.novelai.net/docs
- 모델: https://docs.novelai.net/en/image/models
- Opus 및 Anlas: https://docs.novelai.net/en/subscription/

확인일: 2026-10-23 (한국 시간). API의 모델별 동작과 서비스 비용 정책은 변경될 수 있다.
