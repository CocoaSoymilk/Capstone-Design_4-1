import streamlit as st
import pandas as pd
import openai
import json
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# 페이지 설정
st.set_page_config(
    page_title="리뷰케어 대시보드", 
    page_icon="🎯", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 커스텀 CSS 스타일
st.markdown("""
<style>
    /* 메인 컨테이너 스타일 */
    .main > div {
        padding-top: 2rem;
    }
    
    /* 헤더 스타일 */
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
    }
    
    /* 카드 스타일 */
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #e0e6ed;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        text-align: center;
        margin: 0.5rem 0;
    }
    
    /* 리뷰 카드 스타일 */
    .review-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 1.5rem;
        border-radius: 12px;
        margin: 1rem 0;
        border-left: 4px solid #667eea;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    
    .urgent-review {
        background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%);
        border-left: 4px solid #ff6b6b;
    }
    
    .medium-review {
        background: linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%);
        border-left: 4px solid #ffa726;
    }
    
    .low-review {
        background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
        border-left: 4px solid #26c6da;
    }
    
    /* 버튼 스타일 */
    .stButton > button {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: transform 0.2s;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
    }
    
    /* 사이드바 스타일 */
    .css-1d391kg {
        background: linear-gradient(180deg, #667eea 0%, #764ba2 100%);
    }
    
    /* 메트릭 값 스타일 */
    .metric-value {
        font-size: 2.5rem;
        font-weight: bold;
        color: #667eea;
    }
    
    .metric-label {
        font-size: 0.9rem;
        color: #666;
        font-weight: 500;
    }
    
    /* 범주 태그 스타일 */
    .category-tag {
        display: inline-block;
        padding: 0.25rem 0.6rem;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 500;
        margin: 0.2rem;
        background: #f8f9fa;
        color: #495057;
        border: 1px solid #e9ecef;
    }
</style>
""", unsafe_allow_html=True)

# API 키 설정
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
openai.api_key = OPENAI_API_KEY

# 헤더
st.markdown("""
<div class="main-header">
    <h1>🎯 리뷰케어 대시보드</h1>
    <p>AI 기반 긴급도 분석 · 카테고리 분류 · 자동 답변 생성</p>
</div>
""", unsafe_allow_html=True)

# 사이드바
with st.sidebar:
    st.markdown("### 📊 분석 설정")
    
    uploaded_file = st.file_uploader(
        "CSV 파일 업로드", 
        type=['csv'],
        help="필수 컬럼: content, score, thumbsUpCount, at"
    )
    
    if uploaded_file:
        st.success("✅ 파일 업로드 완료!")
        
        N = st.slider(
            "분석할 리뷰 개수", 
            min_value=1, 
            max_value=50, 
            value=10,
            help="더 많은 리뷰를 분석할수록 시간이 오래 걸립니다"
        )
        
        st.markdown("### 🎨 스타일 설정")
        answer_style = st.selectbox(
            "답변 스타일",
            ['공감 중심', '문제 원인 상세', '고객센터 안내'],
            help="생성될 답변의 톤앤매너를 선택하세요"
        )

def read_csv_with_encoding(file):
    for enc in ["utf-8-sig", "utf-8", "cp949", "euc-kr", "latin1"]:
        try:
            file.seek(0)
            df = pd.read_csv(file, encoding=enc)
            if not df.empty:
                return df
        except Exception:
            continue
    st.error("❌ CSV 파일을 읽을 수 없습니다.")
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

def get_urgency_class(urgency):
    if urgency >= 0.7:
        return "urgent-review"
    elif urgency >= 0.4:
        return "medium-review"
    else:
        return "low-review"

def get_category_class(category):
    category_classes = {
        'BM': 'cat-bm',
        '기술': 'cat-tech',
        '운영': 'cat-ops',
        'UX': 'cat-ux',
        '콘텐츠': 'cat-content',
        '기타': 'cat-etc'
    }
    return category_classes.get(category, 'cat-etc')

if uploaded_file:
    df = read_csv_with_encoding(uploaded_file)
    
    if df is None or df.empty or 'content' not in df.columns or 'score' not in df.columns or 'thumbsUpCount' not in df.columns:
        st.error("❌ 필수 컬럼이 없습니다. (필수: content, score, thumbsUpCount, at)")
        st.stop()
    
    if 'at' in df.columns:
        df['at'] = pd.to_datetime(df['at'], errors='coerce')
    else:
        df['at'] = pd.Timestamp.now()

    # 메트릭 카드들
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{len(df):,}</div>
            <div class="metric-label">📝 총 리뷰 수</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        avg_score = df['score'].mean()
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{avg_score:.1f}★</div>
            <div class="metric-label">⭐ 평균 별점</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{N}</div>
            <div class="metric-label">🔍 분석 대상</div>
        </div>
        """, unsafe_allow_html=True)

    # 분석 시작
    with st.spinner("🤖 AI가 리뷰를 분석하고 있습니다..."):
        preview = df.head(N).copy()
        
        # 진행률 표시
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 카테고리 분석
        status_text.text("📂 카테고리 분류 중...")
        preview['category'] = extract_category(preview['content'])
        progress_bar.progress(50)
        
        # 긴급도 분석
        status_text.text("🚨 긴급도 분석 중...")
        urg, reasons = [], []
        for i, (_, row) in enumerate(preview.iterrows()):
            u, r = get_llm_urgency(row)
            urg.append(u)
            reasons.append(r)
            progress_bar.progress(50 + (i + 1) * 50 // len(preview))
        
        preview['urgency'] = urg
        preview['reason'] = reasons
        progress_bar.progress(100)
        status_text.text("✅ 분석 완료!")
    
    preview = preview.sort_values('urgency', ascending=False).reset_index(drop=True)
    criticals = preview.head(10)
    
    st.markdown("## 🚨 긴급도 상위 리뷰 Top 10")
    
    # 탭으로 구분
    tab1, tab2, tab3 = st.tabs(["📋 리뷰 목록", "💬 답변 생성", "📊 통계 분석"])
    
    with tab1:
        for idx, row in criticals.iterrows():
            urgency_class = get_urgency_class(row['urgency'])
            category_class = get_category_class(row['category'])
            
            # 긴급도에 따른 이모지
            urgency_emoji = "●" if row['urgency'] >= 0.7 else "●" if row['urgency'] >= 0.4 else "●"
            urgency_color = "#dc3545" if row['urgency'] >= 0.7 else "#fd7e14" if row['urgency'] >= 0.4 else "#28a745"
            
            st.markdown(f"""
            <div class="review-card {urgency_class}">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                    <div>
                        <strong>{urgency_emoji} 긴급도: {row['urgency']:.2f}</strong>
                        <span class="category-tag {category_class}">{row['category']}</span>
                    </div>
                    <div style="color: #666;">
                        {str(row['score'])}★ | 👍 {str(row['thumbsUpCount'])}
                    </div>
                </div>
                <div style="margin-bottom: 1rem; line-height: 1.6;">
                    {str(row['content'])[:200]}{'...' if len(str(row['content'])) > 200 else ''}
                </div>
                <div style="font-size: 0.9rem; color: #666;">
                    📅 {row['at'].strftime('%Y-%m-%d %H:%M') if pd.notna(row['at']) else 'N/A'} | 
                    💭 {row['reason']}
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    with tab2:
        st.markdown("### 💬 AI 답변 생성기")
        
        # 선택된 리뷰 표시
        if 'selected_review_idx' not in st.session_state:
            st.session_state.selected_review_idx = 0
        
        selected_review = criticals.iloc[st.session_state.selected_review_idx]
        
        st.markdown("#### 📝 선택된 리뷰")
        st.markdown(f"""
        <div style="background: #f8f9fa; padding: 1rem; border-radius: 6px; border-left: 4px solid #495057; margin-bottom: 1rem;">
            <div style="margin-bottom: 0.5rem;">
                <strong>긴급도: {selected_review['urgency']:.2f}</strong> | 
                <strong>카테고리: {selected_review['category']}</strong> | 
                <strong>별점: {selected_review['score']}★</strong>
            </div>
            <div style="color: #212529;">
                {str(selected_review['content'])}
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown("#### 🎨 답변 스타일 선택")
            selected_style = st.radio(
                "스타일을 선택하세요:",
                ['공감 중심', '문제 원인 상세', '고객센터 안내'],
                horizontal=False,
                help="답변의 톤앤매너를 선택하세요"
            )
        
        with col2:
            st.markdown("#### ✨ 답변 생성")
            if st.button("AI 답변 생성", use_container_width=True, type="primary"):
                review_content = str(selected_review['content'])
                
                style_dict = {
                    '공감 중심': '이용자의 감정에 최대한 공감하고 불편을 인정하는 답변',
                    '문제 원인 상세': '문제 원인에 대해 상세히 설명하는 답변',
                    '고객센터 안내': '문제를 고객센터에서 도와드릴 수 있다는 안내를 중심으로 작성'
                }
                
                prompt = (
                    f"리뷰: \"{review_content}\"\n"
                    f"답변 스타일: {style_dict[selected_style]}\n"
                    "위 리뷰에 대해 CS 담당자 입장에서 공식적이고 중립적으로 답변하라. "
                    "공감, 사과, 해결방안, 후속 안내를 포함하며, "
                    "'현질', '현금박치기', '쪼렙', '오지게' 등 은어·비속어·비공식/은유적 표현은 반드시 '유료 결제', '과금', '유료 아이템 구매', '초보자', '매우' 등 공식적이고 중립적인 용어로 순화하여 답변하라."
                )
                
                with st.spinner("🤖 답변 생성 중..."):
                    resp = openai.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": "너는 게임 CS 담당자이며 답변 시 반드시 비공식어를 순화할 것."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.1,
                        max_tokens=500
                    )
                    answer = resp.choices[0].message.content
                    
                    st.markdown("#### 📋 생성된 답변")
                    st.text_area(
                        "답변 내용",
                        value=answer,
                        height=200,
                        help="생성된 답변을 복사하여 사용하세요"
                    )
    
    with tab3:
        st.markdown("### 📊 분석 결과 통계")
        
        # 서브탭으로 구분
        subtab1, subtab2, subtab3 = st.tabs(["📈 기본 통계", "📅 날짜별 분석", "🔍 심화 분석"])
        
        with subtab1:
            col1, col2 = st.columns(2)
            
            with col1:
                # 별점 분포
                score_counts = preview['score'].value_counts().sort_index()
                fig_score = px.bar(
                    x=score_counts.index, 
                    y=score_counts.values,
                    title="⭐ 별점 분포",
                    labels={'x': '별점', 'y': '리뷰 수'},
                    color=score_counts.values,
                    color_continuous_scale='RdYlGn_r'
                )
                fig_score.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font_family="Arial"
                )
                st.plotly_chart(fig_score, use_container_width=True)
            
            with col2:
                # 카테고리 분포
                cat_counts = preview['category'].value_counts()
                fig_cat = px.pie(
                    values=cat_counts.values,
                    names=cat_counts.index,
                    title="📂 문제 범주 분포",
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                fig_cat.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font_family="Arial"
                )
                st.plotly_chart(fig_cat, use_container_width=True)
            
            # 긴급도 히스토그램
            fig_urgency = px.histogram(
                preview, 
                x='urgency', 
                nbins=20,
                title="🚨 긴급도 분포",
                labels={'urgency': '긴급도', 'count': '리뷰 수'},
                color_discrete_sequence=['#667eea']
            )
            fig_urgency.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font_family="Arial"
            )
            st.plotly_chart(fig_urgency, use_container_width=True)
        
        with subtab2:
            st.markdown("#### 📅 시간대별 리뷰 분석")
            
            # 날짜 데이터 처리
            preview_with_date = preview.copy()
            preview_with_date['date'] = pd.to_datetime(preview_with_date['at']).dt.date
            preview_with_date['hour'] = pd.to_datetime(preview_with_date['at']).dt.hour
            preview_with_date['weekday'] = pd.to_datetime(preview_with_date['at']).dt.day_name()
            
            col1, col2 = st.columns(2)
            
            with col1:
                # 일별 리뷰 수 및 평균 긴급도
                daily_stats = preview_with_date.groupby('date').agg({
                    'urgency': ['count', 'mean'],
                    'score': 'mean'
                }).round(2)
                daily_stats.columns = ['리뷰_수', '평균_긴급도', '평균_별점']
                daily_stats = daily_stats.reset_index()
                
                # 일별 리뷰 수와 긴급도
                fig_daily = go.Figure()
                fig_daily.add_trace(go.Scatter(
                    x=daily_stats['date'],
                    y=daily_stats['리뷰_수'],
                    mode='lines+markers',
                    name='리뷰 수',
                    line=dict(color='#667eea', width=3),
                    yaxis='y'
                ))
                fig_daily.add_trace(go.Scatter(
                    x=daily_stats['date'],
                    y=daily_stats['평균_긴급도'],
                    mode='lines+markers',
                    name='평균 긴급도',
                    line=dict(color='#ff6b6b', width=3),
                    yaxis='y2'
                ))
                fig_daily.update_layout(
                    title="📅 일별 리뷰 수 & 평균 긴급도",
                    xaxis_title="날짜",
                    yaxis=dict(title="리뷰 수", side="left"),
                    yaxis2=dict(title="평균 긴급도", side="right", overlaying="y"),
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font_family="Arial"
                )
                st.plotly_chart(fig_daily, use_container_width=True)
            
            with col2:
                # 요일별 분포
                weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                weekday_korean = ['월', '화', '수', '목', '금', '토', '일']
                weekday_stats = preview_with_date.groupby('weekday')['urgency'].agg(['count', 'mean']).round(2)
                weekday_stats = weekday_stats.reindex(weekday_order)
                weekday_stats['weekday_kr'] = weekday_korean
                
                fig_weekday = px.bar(
                    x=weekday_stats['weekday_kr'],
                    y=weekday_stats['count'],
                    title="📆 요일별 리뷰 수",
                    labels={'x': '요일', 'y': '리뷰 수'},
                    color=weekday_stats['mean'],
                    color_continuous_scale='Reds'
                )
                fig_weekday.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font_family="Arial"
                )
                st.plotly_chart(fig_weekday, use_container_width=True)
            
            # 시간대별 분포
            hourly_stats = preview_with_date.groupby('hour').agg({
                'urgency': ['count', 'mean']
            }).round(2)
            hourly_stats.columns = ['리뷰_수', '평균_긁급도']
            hourly_stats = hourly_stats.reset_index()
            
            fig_hourly = px.line(
                hourly_stats,
                x='hour',
                y='리뷰_수',
                title="🕐 시간대별 리뷰 분포",
                labels={'hour': '시간', '리뷰_수': '리뷰 수'},
                markers=True
            )
            fig_hourly.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font_family="Arial"
            )
            st.plotly_chart(fig_hourly, use_container_width=True)
            
            # 날짜별 카테고리 히트맵
            if len(daily_stats) > 1:
                date_category = preview_with_date.groupby(['date', 'category']).size().unstack(fill_value=0)
                
                fig_heatmap = px.imshow(
                    date_category.T,
                    title="🗓️ 날짜별 카테고리 분포 히트맵",
                    labels=dict(x="날짜", y="카테고리", color="리뷰 수"),
                    color_continuous_scale='Blues'
                )
                fig_heatmap.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font_family="Arial"
                )
                st.plotly_chart(fig_heatmap, use_container_width=True)
        
        with subtab3:
            st.markdown("#### 🔍 심화 분석")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # 카테고리별 긴급도 박스플롯
                fig_box = px.box(
                    preview,
                    x='category',
                    y='urgency',
                    title="📊 카테고리별 긴급도 분포",
                    labels={'category': '카테고리', 'urgency': '긴급도'},
                    color='category',
                    color_discrete_sequence=px.colors.qualitative.Set3
                )
                fig_box.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font_family="Arial"
                )
                st.plotly_chart(fig_box, use_container_width=True)
                
                # 카테고리별 평균 지표
                category_stats = preview.groupby('category').agg({
                    'urgency': 'mean',
                    'score': 'mean',
                    'thumbsUpCount': 'mean'
                }).round(2)
                
                st.markdown("##### 📋 카테고리별 평균 지표")
                st.dataframe(
                    category_stats,
                    column_config={
                        "urgency": st.column_config.ProgressColumn(
                            "평균 긴급도",
                            help="카테고리별 평균 긴급도",
                            min_value=0,
                            max_value=1,
                        ),
                        "score": st.column_config.NumberColumn(
                            "평균 별점",
                            format="%.1f ⭐"
                        ),
                        "thumbsUpCount": st.column_config.NumberColumn(
                            "평균 추천수",
                            format="%.0f 👍"
                        )
                    },
                    use_container_width=True
                )
            
            with col2:
                # 별점 vs 긴급도 산점도
                fig_scatter = px.scatter(
                    preview,
                    x='score',
                    y='urgency',
                    size='thumbsUpCount',
                    color='category',
                    title="⭐ 별점 vs 긴급도 관계",
                    labels={'score': '별점', 'urgency': '긴급도', 'thumbsUpCount': '추천수'},
                    hover_data=['category']
                )
                fig_scatter.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font_family="Arial"
                )
                st.plotly_chart(fig_scatter, use_container_width=True)
                
                # 추천수 구간별 분석
                preview['thumbs_range'] = pd.cut(
                    preview['thumbsUpCount'], 
                    bins=[0, 10, 50, 100, float('inf')], 
                    labels=['~10', '11~50', '51~100', '100+']
                )
                
                thumbs_stats = preview.groupby('thumbs_range').agg({
                    'urgency': 'mean',
                    'score': 'mean'
                }).round(2)
                
                fig_thumbs = px.bar(
                    x=thumbs_stats.index,
                    y=thumbs_stats['urgency'],
                    title="👍 추천수 구간별 평균 긴급도",
                    labels={'x': '추천수 구간', 'y': '평균 긴급도'},
                    color=thumbs_stats['urgency'],
                    color_continuous_scale='Reds'
                )
                fig_thumbs.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font_family="Arial"
                )
                st.plotly_chart(fig_thumbs, use_container_width=True)

else:
    # 빈 상태 표시
    st.markdown("""
    <div style="text-align: center; padding: 4rem; color: #666;">
        <div style="font-size: 4rem; margin-bottom: 1rem;">📂</div>
        <h3>CSV 파일을 업로드해주세요</h3>
        <p>리뷰 데이터 분석을 시작하려면 왼쪽 사이드바에서 파일을 업로드하세요.</p>
        <small>필수 컬럼: content, score, thumbsUpCount, at</small>
    </div>
    """, unsafe_allow_html=True)
