import streamlit as st
import pandas as pd
import openai
import json
import matplotlib.pyplot as plt

# Streamlit Cloud에선 st.secrets["OPENAI_API_KEY"] 권장
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]

openai.api_key = OPENAI_API_KEY

st.set_page_config(page_title="리뷰케어 긴급 리뷰 대시보드", layout="wide")
st.title("리뷰케어: 긴급도·추천수·범주 리뷰 모니터링 & 자동 답변")

uploaded_file = st.file_uploader("CSV 파일 업로드 (필수: content, score, thumbsUpCount, at)", type=['csv'])

def read_csv_with_encoding(file):
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

def custom_urgency(score, thumbs, score_max=5, thumbs_max=1000):
    try:
        s = float(score)
    except:
        s = 3.0
    try:
        t = int(thumbs)
    except:
        t = 0
    score_term = (score_max - s) / (score_max - 1)
    thumbs_term = min(t / thumbs_max, 1.0)
    urgency = 0.35 * score_term + 0.65 * thumbs_term
    return round(urgency, 3)

@st.cache_data(show_spinner=False)
def extract_category(contents):
    cat_list = []
    for content in contents:
        prompt = (
            "너는 게임 CS 담당자다. 아래 리뷰에 대해 문제의 범주(category)를 'BM', '기술', '운영', 'UX', '콘텐츠' 중 가장 적합한 한 단어로만 반환해라. "
            "카테고리 외 설명, 문장, 마침표 없이 딱 한 단어만. "
            f"리뷰: \"{content}\""
        )
        resp = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "카테고리 단어만 반환"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=10
        )
        out = resp.choices[0].message.content.strip()
        if out not in ['BM', '기술', '운영', 'UX', '콘텐츠']:
            out = '기타'
        cat_list.append(out)
    return cat_list

def get_llm_reason(row):
    content = str(row['content'])
    score = str(row['score'])
    thumbs = str(row['thumbsUpCount'])
    prompt = (
        "아래 리뷰에 대해, 별점이 낮고 추천수가 높으면 더욱 시급하다고 판단한다. "
        "긴급도를 0~1(실수)로, 이유를 한글 한 문장으로, 예시와 같이 JSON만 반환해라. "
        "예시: {\"urgency\":0.9,\"reason\":\"1점이면서 추천수가 매우 높음\"} "
        "코드블록, 설명, 다른 문구 없이 JSON만 반환.\n"
        f"리뷰 평점: {score}★, 추천수: {thumbs}\n리뷰: \"{content}\""
    )
    resp = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "예시처럼 JSON만 반환"},
            {"role": "user", "content": prompt}
        ],
        temperature=0.12,
        max_tokens=120
    )
    out = resp.choices[0].message.content.strip()
    try:
        if out.startswith("```"):
            out = out.split("```")[1].strip()
        out = out.replace("'", "\"")
        json_start = out.find("{")
        json_end = out.rfind("}") + 1
        out = out[json_start:json_end]
        js = json.loads(out)
        return js.get('urgency', 0.0), js.get('reason', '분석실패')
    except Exception:
        return custom_urgency(score, thumbs), "긴급도 자동계산"

if uploaded_file:
    df = read_csv_with_encoding(uploaded_file)
    if df is None or df.empty or 'content' not in df.columns or 'score' not in df.columns or 'thumbsUpCount' not in df.columns:
        st.error("CSV 파일에 데이터가 없거나 필수 컬럼이 없습니다. (필수: content, score, thumbsUpCount, at)")
        st.stop()
    if 'at' in df.columns:
        df['at'] = pd.to_datetime(df['at'], errors='coerce')
    else:
        df['at'] = pd.Timestamp.now()

    st.info("긴급도/추천수/범주 분석을 시작합니다.")
    N = st.slider("긴급도 산출할 리뷰 개수(최대 50개 권장)", 1, min(50, len(df)), 10)
    preview = df.head(N).copy()
    preview['category'] = extract_category(preview['content'])
    urg, reasons = [], []
    with st.spinner("긴급도·이유 분석 중..."):
        for _, row in preview.iterrows():
            u, r = get_llm_reason(row)
            urg.append(u)
            reasons.append(r)
    preview['urgency'] = urg
    preview['reason'] = reasons

    preview = preview.sort_values('urgency', ascending=False).reset_index(drop=True)
    criticals = preview.head(10)

    st.subheader("긴급도+추천수+범주 상위 리뷰 (Top 10)")
    col1, col2 = st.columns([2, 3])
    with col1:
        for idx, row in criticals.iterrows():
            st.markdown(f"**{row['at']} - {str(row['score'])}★ / 추천수:{str(row['thumbsUpCount'])}**")
            st.write(str(row['content']))
            st.caption(
                f"긴급도: {row['urgency']:.2f} / 문제범주: {row['category']}"
            )
            st.divider()

    with col2:
        sel_idx = st.number_input(
            "몇 번째 리뷰에 답변할까요? (1~10)", 
            min_value=1, 
            max_value=min(10, len(criticals)), 
            value=1, step=1
        ) - 1
        selected = criticals.iloc[sel_idx]
        review_content = str(selected['content'])
        st.markdown("### 리뷰\n" + review_content)
        st.markdown(f"> **문제 범주:** {selected['category']}")
        st.markdown("> **답변 가이드라인**\n- 공감(불편 인정)\n- 구체적 사과\n- 원인 설명(가능한 경우)\n- 조치 예정 or 고객센터 유도\n- 친근한 마무리\n")
        style = st.radio(
            "답변 스타일을 선택하세요:",
            ['공감 중심', '문제 원인 상세', '고객센터 안내', '최대한 자세히'],
            horizontal=True
        )
        style_dict = {
            '공감 중심': '이용자의 감정에 최대한 공감하고 불편을 인정하는 답변',
            '문제 원인 상세': '문제 원인에 대해 상세히 설명하는 답변',
            '고객센터 안내': '문제를 고객센터에서 도와드릴 수 있다는 안내를 중심으로 작성',
            '최대한 자세히': '최대한 자세하게 문제 해결 안내 및 후속조치 안내'
        }
        selected_guide = style_dict[style]
        answer = ""
        if st.button("선택한 스타일로 답변 생성"):
            prompt = (
                f"리뷰: \"{review_content}\"\n"
                f"답변 스타일: {selected_guide}\n"
                "위 리뷰에 대해 CS 담당자 입장에서 공식적이고 중립적으로 답변하라. "
                "공감, 사과, 해결방안, 후속 안내를 포함하며, 은어/비속어는 공식적으로 순화해라."
            )
            resp2 = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "너는 게임 CS 담당자이며 답변 시 반드시 비공식어를 순화할 것."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.23,
                max_tokens=350
            )
            answer = resp2.choices[0].message.content
        st.text_area("추천 답변 예시", value=answer, height=210)

    # matplotlib 그래프
    import matplotlib.pyplot as plt
    st.subheader("리뷰 통계")
    fig1, ax1 = plt.subplots()
    preview['score'] = preview['score'].astype(str)
    preview['score'].value_counts().sort_index().plot(kind='bar', ax=ax1)
    ax1.set_xlabel('별점')
    ax1.set_ylabel('리뷰 수')
    ax1.set_xticklabels(ax1.get_xticklabels(), rotation=0)
    st.pyplot(fig1)

    st.subheader("문제 범주 분포")
    fig2, ax2 = plt.subplots()
    preview['category'].value_counts().plot(kind='bar', ax=ax2)
    ax2.set_xlabel('문제 범주')
    ax2.set_ylabel('리뷰 수')
    ax2.set_xticklabels(ax2.get_xticklabels(), rotation=0)
    st.pyplot(fig2)

else:
    st.info("CSV 파일을 업로드하면 자동으로 분석됩니다.")
