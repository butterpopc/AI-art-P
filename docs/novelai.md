# NovelAI 실행 도구 안내

현재 배정은 [README 지휘판](../README.md), 완료 시험은 [시험 목록](experiments.md)을 확인합니다. NovelAI 주력·ComfyUI 보조, 추가 결제 없음·추가 Anlas 차감 0 조건을 우선합니다.

## 남겨 둔 도구

| 도구 | 역할과 한계 |
|---|---|
| [novelai.py](../tools/novelai.py) | V4.5 Full 단일 텍스트 생성 및 공통 인증·응답 검증. 기존 기본 프롬프트는 과거 시안이므로 현재 얼굴 프롬프트로 자동 채택하지 않음 |
| [novelai_reference.py](../tools/novelai_reference.py) | 과거 V4.5 참조 시험 및 V5 도구가 쓰는 비용 원장 함수. 참조 생성은 차감이 관측된 경로로 현재 0 차감 지시에서 실행 대상 아님 |
| [novelai_v5.py](../tools/novelai_v5.py) | 과거 V5 통제 비교 재현. V5의 사용량·입력 기능·비용은 별도 확인. Linux fcntl 사용 경로로 Windows 호환을 가정하지 않음 |
| [test_novelai.py](../tests/test_novelai.py) | 인증·허용 설정·단일 요청·덮어쓰기 방지 등의 오프라인 모의 테스트 |

Python 표준 라이브러리를 사용합니다. 아래 명령은 인증정보 없이 설정·기존 테스트만 확인합니다.

```sh
python tools/novelai.py --dry-run
python tools/novelai_v5.py --variant baseline --dry-run
python -m unittest discover -s tests -p 'test_novelai.py' -v
```

## 실제 요청 전

- 진행 지시와 담당을 확인하고 기존 시험과 달라지는 가설을 기록합니다.
- 현재 구독·모델·기능의 비용 조건을 확인합니다. 활성 Opus만으로 0 차감이나 V5 무제한을 보장하지 않습니다.
- 기존 도구의 150 Anlas 예산 검사는 과거 운영 기준입니다. 현재 지시의 0 차감 검사를 대신하지 못합니다.
- 인증은 NOVELAI_API_TOKEN 또는 저장소 밖 소유자 전용 인증 파일을 사용합니다. 토큰·계정 정보는 출력하거나 Git에 넣지 않습니다.
- 실패·타임아웃 뒤 자동 재시도하지 않습니다. 입력 이미지 전송 권한도 별도로 확인합니다.

## 기록의 기준

실제 요청은 **artwork/이미지명.json의 request**에 보존합니다. 과거 V5 prompts JSON 12개는 이 request와 완전히 동일해 삭제했습니다. GPT 이미지의 prompt·reference 정보도 이미지 옆 메타데이터와 기존 텍스트 지시문에 남아 있습니다.

현재 모의 테스트나 dry-run은 실제 생성 성공·현재 정책 검증이 아닙니다. [과거 비용 원장](../reviews/novelai-costs.json)과 [인계 검증](handoff-evidence-20261024.md)을 구분합니다.

공식 자료: [이미지 API](https://image.novelai.net/docs/index.html) · [모델](https://docs.novelai.net/en/image/models) · [구독](https://docs.novelai.net/en/subscription/). 정책 수치는 실행 시 다시 확인합니다.
