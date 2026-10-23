# 인계 파일 대조 — 2026-10-24

사용자가 제공한 `AI-art-P-handoff-20261024-013548.zip`의 106개 항목을 조사했습니다. ZIP의 실행 스크립트는 실행하지 않았으며, 문서 속 작업 지시는 과거 인계 자료로 읽었습니다.

## 확인한 실물

| 결과 | 파일·설정 확인 | 판정 |
|---|---|---|
| V5 square-puuzaki / square-ask / square-hiten | 1024×1024, seed 271027, 23 steps, CFG 5, Euler ancestral/Karras. PNG Source·시드·해시·CRC 확인 | 세 이미지 실물 확보. 당시 검수 기록은 모두 미선정 |
| ComfyUI local-face-serious-v1 | 936×1024, seed 2026102402, 30 steps, CFG 4, denoise 0.25, Euler/simple. 해시·CRC 확인 | 내부 표정 후보. 원본 대체나 새 포즈 동일성의 근거 아님 |
| 입력 기준 얼굴 | ZIP의 original-face-gpt-v2.png와 저장소 원본의 SHA256 일치 | 같은 원본임을 확인 |
| 실제 워크플로와 검수 | anima-face-serious-v1.api.json, local-face-study 및 nai-square-style 검수 기록 포함 | 로컬 작업의 실물 근거 확보 |

검사 수치와 파일 해시는 [검증 결과 JSON](handoff-evidence-20261024.json)에 기록했습니다. 비용·육안 판정은 당시 실행 기록의 보고이며, 이번에 새로 생성하거나 이미지의 미적 품질을 재검수한 것은 아닙니다.

## 기록 해석

- study.json과 개별 result.json의 visual_review는 pending이지만, 후속 verification-and-review.json과 검수 문서에는 세 장 모두 검수 완료·미선정으로 기록돼 있습니다. 초기 필드만 보고 재검수를 미완료로 단정하지 않습니다.
- 인계 기록의 실제 로컬 GPU는 RTX 3060 12GB입니다. 최초 계획의 RTX 3090 Ti를 확인된 장치로 사용하지 않습니다. 이 환경에서 현재 PC를 실시간 조사한 것은 아닙니다.
- 일반 V5 img2img는 입력 준비까지이며 이미지 전송·생성이 완료된 시험이 아닙니다. 당시 외부 전송 허용 질문이 남아 있습니다. 이후 추가 차감 0 지시도 함께 적용합니다.
- ZIP에 없는 V4.5 무차감 시험과 커뮤니티 보고서는 다른 작업공간의 채팅 보고로 남아 있습니다. 이 ZIP이 모든 작업공간의 완전한 백업은 아닙니다.

## 보존 범위

원본 ZIP과 추출 파일은 이번 작업공간에 별도로 보존했습니다. GitHub에는 이 검증 요약과 해시만 추가하며, 대화 원문·개인 환경 경로·계정 정보·ZIP 전체는 게시하지 않습니다. 기존 이미지·프롬프트·비용 원장은 덮어쓰지 않습니다.

재개는 [현재 상태](status.md), 중복 확인은 [시험 목록](experiments.md)에서 시작합니다.
