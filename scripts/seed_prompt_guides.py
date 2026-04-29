"""
prompt_guides 컬렉션에 모델별 실전 프롬프트 가이드를 직접 저장한다.
실행: uv run python scripts/seed_prompt_guides.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import get_config
from tools.prompt_store import PromptGuideStore

cfg = get_config()
store = PromptGuideStore(
    chroma_path=cfg["chroma_path"],
    embedding_model=cfg.get("embedding_model"),
)

# ──────────────────────────────────────────────────────────────────────────────
GUIDES: list[tuple[str, str]] = [

# ── Stable Diffusion 1.5 ─────────────────────────────────────────────────────
("Stable Diffusion 1.5", """
[Stable Diffusion 1.5 프롬프트 가이드]

## 기본 방식
콤마로 구분한 키워드 태그 나열 방식. 앞쪽 태그일수록 영향력이 크다.
자연어 문장보다 짧고 압축된 키워드 형태가 효과적이다.

## 추천 구조 (순서 중요)
품질 태그 → 피사체 → 외모 세부 → 환경 → 조명 → 스타일

## 품질 태그 (앞에 배치)
masterpiece, best quality, ultra detailed, 8k, sharp focus, high resolution, intricate details

## 가중치 문법
- (keyword) : 1.1배 강조
- (keyword:1.3) : 1.3배 강조 / (keyword:0.8) : 0.8배 약화
- ((keyword)) : 이중 괄호는 약 1.21배
- 권장 범위: 0.5 ~ 1.5 (초과 시 이미지 품질 저하)

## 네거티브 프롬프트 (필수)
lowres, bad anatomy, bad hands, extra fingers, missing fingers, poorly drawn hands,
poorly drawn face, mutation, deformed, blurry, jpeg artifacts, watermark, signature,
text, username, out of frame, extra limbs, cloned face, disfigured, gross proportions,
worst quality, low quality, normal quality, monochrome, grayscale

## CFG Scale 권장값
- 7: 자연스럽고 다양한 결과
- 12: 프롬프트 충실도 높음 (권장 균형점)
- 15-16: 매우 강한 프롬프트 반영 (조명 왜곡 주의)

## 실전 예시 — 인물 포트레이트
masterpiece, best quality, ultra detailed, 1girl, long silver hair, blue eyes,
elegant white dress, sitting in rose garden, soft morning light, bokeh background,
sharp focus, 8k, film grain
Negative: lowres, bad anatomy, bad hands, poorly drawn, watermark, blurry
CFG: 12, Steps: 28, Sampler: DPM++ 2M Karras

## 실전 예시 — 풍경
masterpiece, best quality, ultra detailed, scenic mountain landscape, golden hour,
dramatic clouds, crystal clear river, pine forest, god rays, cinematic lighting,
award winning photography, 8k resolution
Negative: lowres, blurry, watermark, text
CFG: 10, Steps: 25

## 스타일 태그 목록
- 사진: photorealistic, hyperrealistic, DSLR photo, 85mm lens, bokeh
- 회화: oil painting, watercolor, digital painting, impressionist, detailed brush strokes
- 애니: anime style, manga, cel shading, studio ghibli style
- 3D: 3D render, octane render, unreal engine 5, ray tracing
"""),

# ── Stable Diffusion XL ──────────────────────────────────────────────────────
("Stable Diffusion XL", """
[Stable Diffusion XL (SDXL) 프롬프트 가이드]

## SD1.5와의 핵심 차이
SDXL은 강력한 텍스트 인코더를 탑재해 자연어 서술형 프롬프트를 더 잘 이해한다.
태그 나열 방식도 작동하지만, 문장 형태가 더 자연스럽고 정확한 결과를 낸다.

## 추천 구조
[주체 설명] + [환경/배경] + [조명 조건] + [카메라/렌즈] + [스타일 키워드]

## 품질 태그 (간소화)
best quality, ultra detailed, professional photography
(SD1.5처럼 과도한 품질 태그 나열 불필요)

## 가중치 문법
(keyword:1.2) 사용 가능하나 자연어 표현이 더 효과적.
대신 "a prominently visible ...", "with great emphasis on ..." 등 서술 활용.

## 네거티브 프롬프트 (짧아도 충분)
low quality, blurry, distorted, watermark, text

## 권장 해상도
기본: 1024×1024
세로: 832×1216 (인물)
가로: 1216×832 (풍경)
(512×512 사용 시 품질 현저히 저하)

## Refiner 사용 (선택)
Base 모델로 초안 생성 → Refiner로 눈, 피부, 윤곽선 등 세부 개선
denoising_start=0.8 권장

## 실전 예시 — 시네마틱 인물
Cinematic portrait of a Scandinavian woman with freckles, wearing a flowing red dress,
standing in a sunlit wildflower field, soft diffused lighting from overcast sky,
captured with 85mm portrait lens, shallow depth of field focusing on her face,
ultra detailed skin texture, photorealistic, editorial magazine style, best quality
Negative: low quality, blurry, distorted
Sampler: DPM++ 2M Karras, CFG: 7, Resolution: 1024×1024

## 실전 예시 — 환경/건축
An ancient library carved into the side of a mountain cliff, massive stone archways,
thousands of books illuminated by warm candlelight, dust particles floating in the air,
dramatic chiaroscuro lighting, cinematic composition, ultra detailed stonework,
HDR photography style, professional architectural photography
Negative: low quality, blurry
CFG: 7, Steps: 30, Resolution: 1216×832

## CFG Scale 권장값
- 5-7: 창의적이고 다양한 해석
- 7: SDXL 기본 권장값 (균형)
- 9 이상: 과도한 채도·명암 발생 위험
"""),

# ── FLUX.1 ───────────────────────────────────────────────────────────────────
("FLUX.1", """
[FLUX.1 (dev / schnell) 프롬프트 가이드]

## 핵심 차이 — SD/SDXL과 완전히 다른 방식
- 가중치 문법 ((keyword:1.2), (emphasis)) 완전 무시됨 — 사용 금지
- 네거티브 프롬프트 지원 없음 (dev 기준)
- 순수 자연어 서술형 프롬프트만 효과적
- 텍스트 렌더링 능력이 뛰어나 간판·레이블·로고 표현 가능

## 추천 구조
[주체 + 핵심 특성] + [동작/포즈] + [환경 + 분위기] + [조명] + [카메라/스타일]

## 길이 권장
- 최적: 40~80 단어 (한 문단 서술)
- 과도한 태그 나열보다 명확한 한 문장이 더 효과적
- 지나치게 길면 (200단어+) 세부사항 간 충돌 발생

## 강조 방법
가중치 괄호 대신 서술 표현 사용:
- "with a strong focus on ..." → 해당 요소 강조
- "prominently featuring ..." → 두드러지게 표현
- "a close-up of ..." → 해당 부분 크게
- "highly detailed [요소]" → 그 요소를 세밀하게

## 스타일 지정
특정 아티스트 이름 또는 스타일 서술로 지정:
"in the style of Studio Ghibli", "inspired by Monet's impressionism",
"in the aesthetic of 1970s film photography"

## FLUX.1 dev vs schnell
- dev: 높은 품질, 20-30 스텝 필요, 생성 느림
- schnell: 빠른 생성 (1-4 스텝), 품질 약간 낮음, 빠른 프로토타이핑 용

## 실전 예시 — 인물
A serene portrait of a young woman with waist-length black hair, wearing a traditional
Japanese kimono in soft blue and white patterns, sitting by an open shoji window with
morning light streaming across her face, painted in the impressionist style with
visible brushstrokes and warm golden tones, peaceful contemplative expression
Steps: 25, Guidance: 3.5 (dev 기준)

## 실전 예시 — 환경
A vast cyberpunk cityscape viewed from a rooftop at night, neon signs in Korean and
Japanese characters reflecting off rain-soaked streets below, flying vehicles with
light trails, dramatic low-angle perspective, cinematic wide-angle composition,
hyperrealistic photograph quality with sharp focus on the foreground railing
Steps: 28, Guidance: 3.5

## 실전 예시 — 텍스트 포함
A vintage wooden sign hanging above a seaside cafe that reads "HARBOR COFFEE" in
hand-painted letters, weathered wood texture, seagulls in the background, golden
afternoon light, detailed grain and aging effects
(FLUX는 텍스트 렌더링이 정확하므로 이런 사용 적합)

## 흔한 실수
- ❌ "masterpiece, best quality, (beautiful:1.4), ultra detailed" → 효과 없음
- ❌ 네거티브 프롬프트 입력 → 효과 없음
- ✅ 사진작가·감독에게 지시하듯 서술형으로 작성
"""),

# ── Midjourney v6 ────────────────────────────────────────────────────────────
("Midjourney", """
[Midjourney v6 프롬프트 가이드]

## 기본 구조
[주체 묘사] + [환경 및 배경] + [조명 및 분위기] + [스타일/아티스트 레퍼런스] + [파라미터]

## 핵심 파라미터 목록

### 비율 --ar (--aspect)
--ar 16:9  → 가로형 영상/배경
--ar 4:3   → 표준 사각형
--ar 1:1   → 정사각형 (기본값)
--ar 9:16  → 세로형 모바일
--ar 2:3   → 세로 인물 포트레이트

### 스타일화 --stylize (--s) [0-1000]
0: 프롬프트 매우 충실하게 반영, 예술적 해석 최소
100: 기본값 (균형)
500~750: 예술적 스타일 강화, 보다 창의적 해석
1000: 최대 예술적 자유, 프롬프트 정확도 저하

### 다양성 --chaos (--c) [0-100]
0: 4개 이미지가 비슷한 구성 (기본값)
30-50: 적당한 변주
100: 각 이미지가 완전히 다른 해석

### 제외 요소 --no
--no glasses → 안경 제거
--no background people → 배경 인물 제거
--no text → 텍스트 제거

### 스타일 프리셋 --style
--style raw → MJ의 자체 미학 최소화, 프롬프트에 더 충실
(v6 기본값이 이미 --style raw에 가까움)

### 가중치 :: (이중 콜론)
mountain landscape::2 sunset::1
→ 산 풍경을 일몰의 2배 중요도로 처리

### 이미지 레퍼런스
URL 앞에 배치: https://image-url.jpg A woman in similar style --ar 16:9
--iw 0.5~2.0 : 이미지 가중치 (기본 1.0)

## 아티스트 레퍼런스 예시 (효과적인 조합)
- 사실적 판타지: "inspired by Yusuke Murata, intricate line art"
- 시네마틱: "cinematography by Roger Deakins"
- 개념 미술: "concept art by Craig Mullins"
- 초현실주의: "surrealist painting in the style of Salvador Dali"
- 수채화: "watercolor illustration by Yoshitaka Amano"

## 실전 예시 — 판타지 전사
A fierce female knight in ornate obsidian armor, standing on a misty volcanic cliff
at dawn, dramatic orange backlighting, molten lava rivers in the valley below,
epic fantasy art inspired by Yusuke Murata, highly detailed armor engraving,
heroic low-angle composition --ar 16:9 --s 750 --c 10

## 실전 예시 — 시네마틱 포트레이트
Close-up portrait of an elderly fisherman weathered by the sea, deep wrinkles,
kind eyes, wearing a rain-soaked yellow oilskin coat, overcast northern sky,
dramatic Rembrandt lighting, photojournalism style --ar 4:5 --s 200 --style raw

## 실전 예시 — 건축/풍경
Ancient Japanese shrine nestled in a misty bamboo forest at dawn, stone lanterns
with soft glowing light, fallen maple leaves on wet stone path, serene and spiritual
atmosphere, long exposure photography aesthetic --ar 16:9 --s 500

## 프롬프트 작성 팁
1. 가장 중요한 요소를 프롬프트 앞에 배치
2. 감정/분위기 단어 포함: "serene", "epic", "melancholic", "vibrant"
3. 조명 명시: "golden hour", "overcast lighting", "dramatic side lighting"
4. 매체 명시: "oil painting", "35mm film photograph", "digital illustration"
"""),

# ── DALL-E 3 ─────────────────────────────────────────────────────────────────
("DALL-E 3", """
[DALL-E 3 프롬프트 가이드]

## 핵심 특성
- OpenAI GPT-4 기반 텍스트 이해력으로 복잡한 서술도 정확하게 반영
- 자연어 문장 형태 최적화 — 태그 나열 불필요
- ChatGPT와 연동 시 자동 프롬프트 개선(rewrite) 기능 내장
- 네거티브 프롬프트 없음 (대신 "avoid", "without" 등 자연어로 제외)
- 텍스트·로고·간판 렌더링 능력 우수 (짧은 텍스트 기준)

## 추천 구조
[장면 설명] + [주체 세부] + [환경/배경] + [조명/분위기] + [스타일 지정] + [카메라/구도]

## 스타일 지정 방법
"oil painting style", "watercolor illustration", "photorealistic photograph",
"pencil sketch", "Studio Ghibli-inspired animation", "charcoal drawing",
"flat vector illustration", "3D CGI render"

## 사진 용어 활용 (사실적 결과에 효과적)
- 렌즈: "50mm lens", "85mm portrait lens", "wide-angle 24mm"
- 효과: "bokeh background", "shallow depth of field", "film grain"
- 조명: "golden hour light", "Rembrandt lighting", "soft studio lighting", "backlit"
- 필름: "Kodak Portra 400 aesthetic", "Fujifilm color palette"

## 미술 용어 활용
"sfumato shading", "impasto texture", "chiaroscuro contrast",
"pointillism style", "tenebrism lighting"

## 제외 표현 (네거티브 대신)
"without any text", "avoid showing other people", "with no visible brand logos"

## 자동 프롬프트 개선 비활성화 방법
ChatGPT 연동 시 자동 확장을 막으려면:
"I NEED to test how the tool works with exactly this prompt. DO NOT add any detail, just use it AS-IS:"
를 프롬프트 앞에 추가

## 실전 예시 — 감성 인물
A close-up portrait of a smiling elderly Korean grandmother with silver hair pulled
into a bun, sitting by a window with soft morning sunlight streaming across her
gentle face, wearing a traditional light grey hanbok, warm atmospheric lighting,
photorealistic style, shallow depth of field focusing on her eyes, fine details
visible on her hands and facial wrinkles, intimate and peaceful mood
→ 사람의 감정·분위기를 충분히 서술하면 DALL-E 3가 잘 반영함

## 실전 예시 — 개념 일러스트
A whimsical illustration of a tiny lighthouse standing on top of a stack of old books,
surrounded by flying paper cranes, warm magical glow emanating from the lighthouse
beam, soft pastel color palette, children's book illustration style, detailed and
charming, flat art with subtle textures

## 실전 예시 — 건축/공간
The interior of a 1920s Parisian boulangerie at dawn before opening, sunlight just
beginning to stream through dusty windows illuminating floating flour particles,
freshly baked baguettes arranged on wooden shelves, warm amber and cream color tones,
hyperrealistic photography style with grain, 35mm wide-angle composition

## 실전 예시 — 텍스트 포함
A vintage travel poster for the city of Seoul, featuring the Gyeongbokgung Palace
under a dramatic sky, bold art deco typography that reads "VISIT SEOUL" at the top,
rich deep blue and gold color scheme, 1930s graphic design aesthetic
(짧고 명확한 텍스트 → DALL-E 3에서 비교적 정확하게 렌더링됨)

## 주의 사항
- 유명인 이름 직접 사용 불가 (OpenAI 정책)
- 저작권 있는 캐릭터 직접 언급 제한
- 폭력·선정적 콘텐츠 생성 제한
"""),

# ── NovelAI Diffusion ─────────────────────────────────────────────────────────
("NovelAI", """
[NovelAI Diffusion 프롬프트 가이드]

## 핵심 특성
- Danbooru 이미지보드 태그 시스템 기반
- 애니메이션·만화·일러스트 특화 모델
- 태그 순서가 결과에 직접 영향
- 중괄호로 강조, 대괄호로 약화

## 강조/약화 문법
- {{keyword}} : 1.05배 강조 (중괄호 1쌍)
- {{{{keyword}}}} : 중첩할수록 강도 증가
- [keyword] : 대괄호 = 약화
- {keyword} : 소폭 강조

## 추천 태그 구조 (순서 중요)
1. 인원수: 1girl, 2girls, 1boy, solo
2. 품질 태그: {{masterpiece}}, {{best quality}}, {{highly detailed}}
3. 캐릭터: 캐릭터명 (Danbooru 정확한 태그명 사용)
4. 헤어: long hair, silver hair, twintails, braided, ahoge
5. 눈: blue eyes, heterochromia, glowing eyes, half-closed eyes
6. 의상: school uniform, maid outfit, yukata, armor, casual clothes
7. 포즈/표현: standing, sitting, arms behind back, smile, blush
8. 배경: simple background, white background, outdoors, bedroom, cafe
9. 특수 효과: bokeh, sparkle, motion blur, lens flare, depth of field
10. 추가 품질: ultra detailed, intricate details, 4k

## 네거티브 프롬프트 (권장)
lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit,
fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts,
signature, watermark, username, blurry, poorly drawn hands, poorly drawn face,
mutation, deformed, extra limbs, cloned face, disfigured

## Danbooru 태그 정확성
- 정확한 Danbooru 태그 사용 필수 (1000+ 이미지 있는 태그 권장)
- 잘못된 예: "blue eyes girl" → 올바른 예: "1girl, blue eyes"
- 캐릭터명: "hatsune miku" (소문자, Danbooru 기준)
- 의상: "school uniform" → "serafuku" (Danbooru 정식 태그)

## 실전 예시 — 일반 캐릭터
{{{{masterpiece}}}}, {{{{best quality}}}}, {{highly detailed}},
1girl, solo, long silver hair, blue eyes, ahoge, white sundress,
standing on beach at sunset, sea breeze, hair flowing, gentle smile,
golden hour lighting, bokeh, depth of field, cinematic composition
Negative: lowres, bad anatomy, bad hands, poorly drawn, watermark, blurry
CFG: 11, Steps: 28, Sampler: Euler a

## 실전 예시 — 기존 캐릭터 (하츠네 미쿠)
{{{{masterpiece}}}}, {{best quality}}, highly detailed,
1girl, solo, hatsune miku, long cyan twintails, teal eyes,
idol concert outfit, white thighhighs, standing on stage,
dynamic pose, spotlight, sparkle effect, confetti, concert atmosphere,
detailed, intricate patterns on outfit
Negative: lowres, bad quality, worst quality, blurry, deformed
CFG: 12, Steps: 30

## 실전 예시 — 분위기 중심
{{masterpiece}}, {{best quality}}, highly detailed, atmospheric,
1girl, long black hair, white school uniform, sitting by window,
rainy day, raindrops on glass, soft diffused lighting, melancholic mood,
reading a book, cozy warm interior, cold blue exterior contrast,
shallow depth of field, bokeh, photorealistic background
Negative: lowres, bad anatomy, poorly drawn, watermark
CFG: 11, Steps: 25

## 모델 버전별 특성
- NAI v1 (Curated/Full): 초기 모델, anime 특화
- NAI v2: 개선된 해부학, 더 다양한 스타일
- NAI v3: 최신 모델, 자연어 혼용 가능, 세부 표현력 대폭 향상
  → v3에서는 자연어와 태그 혼용 허용: "1girl, she is sitting by a rainy window, {{masterpiece}}"

## 실용 팁
- Danbooru 사이트에서 원하는 스타일의 이미지 태그 직접 확인 가능
- PromptHero, nai.tools에서 검증된 프롬프트 참고
- 캐릭터명 미숙지 시 외모 묘사 태그만으로도 충분히 특정 캐릭터 유도 가능
"""),

]
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    for model_name, guide_text in GUIDES:
        store.save(model=model_name, guide_text=guide_text.strip(), source="user")
        print(f"  저장 완료: {model_name}")

    print(f"\n총 {len(GUIDES)}개 모델 가이드 저장 완료.")
    print("저장된 모델 목록:", store.list_models())
