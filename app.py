import streamlit as st
import pandas as pd
import openai
import json
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import os

# 환경변수: Streamlit Cloud(Secrets)와 .env(로컬) 모두 지원
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Secrets(Cloud) > 환경변수 순서로 불러오기
openai_api_key = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"))
if not openai_api_key:
    st.error("OpenAI API 키가 없습니다! (Secrets 또는 .env 확인)")
    st.stop()
openai.api_key = openai_api_key

st.set_page_config(page_title="리뷰케어 긴급 리뷰 대시보드", layout="wide")
st.title("리뷰케어: 긴급 리뷰 모니터링 & 자동 답변")

uploaded_file = st.file_uploader("CSV 파일 업로드", type=['csv'])

def read_csv_with_encoding(file):
    """여러 인코딩으로 안전하게 읽기"""
    for enc in ["utf-8-sig", "utf-8", "cp949", "euc-kr", "latin1"]:
        try:
            file.seek(0)
            df = pd.read_csv(file, encoding=enc)
            if not df.empty:
                return df
        except Exception:
            continue
    st.error("CSV 파일 인코딩을 알 수 없거나 데이터를 읽지 못했습니다.")
    return None

if uploaded_file:
    df = read_csv_with_encoding(uploaded_file)
    if df is None or df.empty or 'content' not in df.columns or 'score' not in df.columns:
        st.error("CSV 파일에 데이터가 없거나 필수 컬럼이 없습니다. (필수: content, score, at)")
        st.stop()
    # 날짜 컬럼 전처리
    if 'at' in df.columns:
        df['at'] = pd.to_datetime(df['at'], errors='coerce')
    else:
        df['at'] = pd.Timestamp.now()

    def get_urgency(row):
        content = str(row['content'])
        score = str(row['score'])
        # 혹시라도 bytes 타입이면 디코딩
        if isinstance(row['content'], bytes):
            content = row['content'].decode('utf-8', errors='ignore')
        if isinstance(row['score'], bytes):
            score = row['score'].decode('utf-8', errors='ignore')
        prompt = (
            "너는 게임 CS 전담 모델이다. "
            "아래 리뷰에 대해 긴급도를 0~1(실수)로, 이유(reason)를 한글로 1문장으로, "
            "예시와 같이 JSON만 반환해라. 예시: {\"urgency\":0.7,\"reason\":\"1점 리뷰이면서 욕설이 있어 시급\"}. "
            "코드블록, 설명, 다른 문구 없이 JSON만 반환.\n"
            f"리뷰 평점: {score}★\n리뷰: \"{content}\""
        )
        resp = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "예시처럼 JSON만 반환"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=120
        )
        out = str(resp.choices[0].message.content).strip()
        try:
            if out.startswith("```"):
                out = out.split("```")[1].strip()
            out = out.replace("'", "\"")
            json_start = out.find("{")
            json_end = out.rfind("}") + 1
            out = out[json_start:json_end]
            js = json.loads(out)
            return js.get('urgency', 0.0), js.get('reason', '분석실패')
        except Exception as e:
            st.warning(f"파싱 오류: {e}\n출력={out}")
            return 0.0, "분석실패"

    st.info("긴급도 분석이 시작됩니다. 10~20개 미리보기 권장.")
    N = st.slider("긴급도 산출할 리뷰 개수(최대 50개 권장)", 1, min(50, len(df)), 10)
    preview = df.head(N)
    urg, reasons = [], []
    with st.spinner("긴급도 및 이유 분석 중..."):
        for _, row in preview.iterrows():
            u, r = get_urgency(row)
            urg.append(u)
            reasons.append(r)
    preview = preview.copy()
    preview['urgency'] = urg
    preview['reason'] = reasons

    preview = preview.sort_values('urgency', ascending=False).reset_index(drop=True)
    criticals = preview.head(10)

    st.subheader("긴급도 상위 리뷰(Top 10)")
    col1, col2 = st.columns([2, 3])

    with col1:
        for idx, row in criticals.iterrows():
            st.markdown(f"**{row['at']} - {row['score']}★**")
            st.write(str(row['content']))
            st.caption(f"긴급도: {row['urgency']:.2f} / 이유: {row['reason']}")
            st.divider()

    with col2:
        sel_idx = st.number_input("몇 번째 리뷰에 답변할까요? (1~10)", min_value=1, max_value=min(10, len(criticals)), value=1, step=1) - 1
        selected = criticals.iloc[sel_idx]
        review_content = str(selected['content'])
        st.markdown(f"### 리뷰\n{review_content}")
        st.markdown("> **답변 가이드라인**\n- 공감(불편 인정)\n- 구체적 사과\n- 원인 설명(가능한 경우)\n- 조치 예정 or 고객센터 유도\n- 친근한 마무리")
        prompt = (
            f"리뷰: \"{review_content}\"\n"
            "위 리뷰에 대해 CS 담당자 입장에서 답변을 작성할 때, "
            "공감, 사과, 해결방안, 후속 안내를 포함하고, "
            "\"현질\" 등 은어/비공식어/비속어/은유적 표현이 있으면 공식적이고 중립적인 표현으로 순화해서 작성해라. "
            "예시: '현질'→'유료 결제', '과금'→'유료 아이템 구매', '욕설'→'부적절한 언어' 등"
        )
        resp2 = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "너는 게임 CS 담당자이며 답변 시 반드시 비공식어를 순화할 것."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=300
        )
        answer = str(resp2.choices[0].message.content)
        st.text_area("추천 답변 예시(비공식어 자동 순화)", value=answer, height=200)

    st.subheader("리뷰 통계")
    st.bar_chart(preview['score'].value_counts().sort_index())

else:
    st.info("CSV 파일을 업로드하면 자동으로 분석됩니다.")
