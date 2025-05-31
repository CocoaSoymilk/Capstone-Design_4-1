import streamlit as st
import pandas as pd
import openai
import json

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

def get_llm_urgency(row):
    content = str(row['content'])
    score = str(row['score'])
    thumbs = str(row['thumbsUpCount'])
    prompt = (
        "너는 숙련된 게임 CS 분석가다. 아래 게임 리뷰의 전체 내용을 꼼꼼히 읽고, "
        "별점과 추천수, 그리고 리뷰의 전반적인 맥락과 표현을 바탕으로 '이 리뷰가 게임사에 얼마나 시급하게 대응되어야 할지'를 객관적으로 평가해라. "
        "특정 키워드가 없어도 맥락상 서비스 안정성, 신뢰성, 금전적 피해, 다수 이용자의 불편, 반복적 신고, 감정적 호소 등 여러 요인을 종합적으로 고려해 시급도를 판단해라. "
        "별점이 낮거나 추천수가 높거나, 혹은 본문에서 긴급성이 느껴지면 높은 점수를 주고, 단순 의견 또는 반복 이슈가 아니면 낮은 점수를 주라. "
        "결과는 반드시 아래 예시처럼 JSON만 반환해라. "
        "예시: {\"urgency\":0.97,\"reason\":\"1점 리뷰에 많은 추천수가 있고, 환불을 강하게 요청함\"} "
        "예시: {\"urgency\":0.5,\"reason\":\"게임 시스템 건의로, 긴급 대응 필요는 낮음\"} "
        "코드블록, 설명, 다른 문구 없이 JSON만 반환.\n"
        f"리뷰 평점: {score}★, 추천수: {thumbs}\n리뷰: \"{content}\""
    )
    try:
        resp = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "예시처럼 JSON만 반환"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.11,
            max_tokens=200
        )
        out = resp.choices[0].message.content.strip()
        if out.startswith("```"):
            out = out.split("```")[1].strip()
        out = out.replace("'", "\"")
        json_start = out.find("{")
        json_end = out.rfind("}") + 1
        out = out[json_start:json_end]
        js = json.loads(out)
        return js.get('urgency', 0.0), js.get('reason', '분석실패')
    except Exception:
        return 0.5, "분석실패"

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
            u, r = get_llm_urgency(row)
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
            ['공감 중심', '문제 원인 상세', '고객센터 안내'],
            horizontal=True
        )
        style_dict = {
            '공감 중심': '이용자의 감정에 최대한 공감하고 불편을 인정하는 답변',
            '문제 원인 상세': '문제 원인에 대해 상세히 설명하는 답변',
            '고객센터 안내': '문제를 고객센터에서 도와드릴 수 있다는 안내를 중심으로 작성'
        }
        selected_guide = style_dict[style]
        answer = ""
        if st.button("선택한 스타일로 답변 생성"):
            prompt = (
                f"리뷰: \"{review_content}\"\n"
                f"답변 스타일: {selected_guide}\n"
                "위 리뷰에 대해 CS 담당자 입장에서 공식적이고 중립적으로 답변하라. "
                "공감, 사과, 해결방안, 후속 안내를 포함하며, "
                "'현질', '현금박치기', '쪼렙', '오지게' 등 은어·비속어·비공식/은유적 표현은 반드시 '유료 결제', '과금', '유료 아이템 구매', '초보자', '매우' 등 공식적이고 중립적인 용어로 순화하여 답변하라."
            )
            resp2 = openai.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "너는 게임 CS 담당자이며 답변 시 반드시 비공식어를 순화할 것."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )
            answer = resp2.choices[0].message.content
        st.text_area("추천 답변 예시", value=answer, height=210)

    st.subheader("리뷰 통계")
    st.bar_chart(preview['score'].value_counts().sort_index())

    st.subheader("문제 범주 분포")
    st.bar_chart(preview['category'].value_counts())

else:
    st.info("CSV 파일을 업로드하면 자동으로 분석됩니다.")
