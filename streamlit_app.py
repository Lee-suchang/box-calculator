import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime

# --- 데이터 구조 정의 (사용자 기준표에 맞게 수정) ---

# 1. 기본 원지 데이터: {원지명: {'원지값': 원/kg, '평량': g/㎡}}
# 사용자의 엑셀 기준값을 역산하여 SK180의 원지값을 650원으로 수정
paper_data_default = {
    "S120": {"원지값": 580, "평량": 120},
    "B150": {"원지값": 560, "평량": 150},
    "K180": {"원지값": 650, "평량": 180},
    "K200": {"원지값": 630, "평량": 200},
    "SK180": {"원지값": 650, "평량": 180}, # 기존 750 -> 650원으로 수정
    "KLB175": {"원지값": 720, "평량": 175},
    "WK180": {"원지값": 850, "평량": 180}
}

# 2. 골 종류별 단조율 (기존 로직 유지)
corrugated_factor_map = {
    "E골": 1.3,
    "B골": 1.4,
    "A골": 1.6,
    "DW골(A+B)": 1.6 + 1.4
}

# 3. 골 종류별 ㎡당 가공비 (기존 로직 유지 - 사용자의 기준표와 일치)
processing_cost_per_sqm_map = {
    "E골": 15,
    "B골": 10,
    "A골": 20,
    "DW골(A+B)": 29
}

# 4. 인쇄 도수별 비용 (기존 로직 유지)
print_cost_map = {
    "0도": 0,
    "1도": 10000,
    "2도": 20000,
    "4도": 35000
}


# --- 계산 함수 (로스율 반영하여 최종 수정) ---

def calculate_price_new(
        장, 폭, 고, 미미, 폭수, 여유값, # 기본 입력
        board_spec, paper_data, # 원단 사양
        flute_grade, print_color, # 공정 사양
        die_cut_unit, glue_unit, extra_unit, loss_rate, qty, vat # 비용 및 수량 (loss_rate 추가)
):
    # 1. 전폭 계산 (박스 폭 + 박스 높이)
    전폭 = 폭 + 고

    # 2. 실제지폭 계산 (전폭 * 폭수 + 여유값)
    실제지폭 = (전폭 * 폭수) + 여유값

    # 3. 실제지폭 유효성 검사 (2500mm 초과 확인)
    if 실제지폭 > 2500:
        error_message = f"오류: 계산된 실제지폭({실제지폭}mm)이 최대 허용치 2500mm를 초과합니다. '폭수' 또는 '여유값'을 조정해주세요."
        return None, {"오류": error_message}

    # 4. 전장 계산 ((장 + 폭) * 2 + 미미)
    전장 = (장 + 폭) * 2 + 미미

    # 5. 소요량 계산 (박스 1개당 면적, ㎡)
    area_per_box = (전장 * 전폭) / 1_000_000

    # 6. ㎡당 원단비 계산 (로스율 적용)
    material_cost_per_sqm_base = 0 # 로스 적용 전 원단비

    # 각 원지 층의 단가 계산
    # 표면지
    paper_outer = board_spec['표면지']
    price_kg_outer = paper_data[paper_outer]['원지값']
    grammage_kg_outer = paper_data[paper_outer]['평량'] / 1000
    material_cost_per_sqm_base += price_kg_outer * grammage_kg_outer

    # 이면지
    paper_inner = board_spec['이면지']
    price_kg_inner = paper_data[paper_inner]['원지값']
    grammage_kg_inner = paper_data[paper_inner]['평량'] / 1000
    material_cost_per_sqm_base += price_kg_inner * grammage_kg_inner

    # 골심지 및 중심지
    if "DW" in flute_grade:
        # 골심지 A
        paper_flute_A = board_spec['골심지A']
        price_kg_flute_A = paper_data[paper_flute_A]['원지값']
        grammage_kg_flute_A = paper_data[paper_flute_A]['평량'] / 1000
        factor_A = 1.6
        material_cost_per_sqm_base += price_kg_flute_A * grammage_kg_flute_A * factor_A

        # 골심지 B
        paper_flute_B = board_spec['골심지B']
        price_kg_flute_B = paper_data[paper_flute_B]['원지값']
        grammage_kg_flute_B = paper_data[paper_flute_B]['평량'] / 1000
        factor_B = 1.4
        material_cost_per_sqm_base += price_kg_flute_B * grammage_kg_flute_B * factor_B

        # 중심지
        paper_center = board_spec['중심지']
        price_kg_center = paper_data[paper_center]['원지값']
        grammage_kg_center = paper_data[paper_center]['평량'] / 1000
        material_cost_per_sqm_base += price_kg_center * grammage_kg_center
    else: # 편면골
        paper_flute = board_spec['골심지']
        price_kg_flute = paper_data[paper_flute]['원지값']
        grammage_kg_flute = paper_data[paper_flute]['평량'] / 1000
        factor = corrugated_factor_map.get(flute_grade, 1.4)
        material_cost_per_sqm_base += price_kg_flute * grammage_kg_flute * factor

    # --- [핵심 수정] 로스율을 적용하여 최종 ㎡당 원단비(원재료비) 계산 ---
    material_cost_per_sqm = material_cost_per_sqm_base * (1 + (loss_rate / 100))

    # 7. 박스 1개당 총 비용 계산
    # 7-1. 원단비 (1개당)
    material_cost_per_box = material_cost_per_sqm * area_per_box

    # 7-2. 가공비 (1개당)
    processing_cost_sqm = processing_cost_per_sqm_map.get(flute_grade, 0)
    processing_cost_per_box = (processing_cost_sqm * area_per_box) + die_cut_unit + glue_unit + extra_unit

    # 7-3. 총 비용 (수량 적용 전, 1개당)
    cost_per_box_before_print = material_cost_per_box + processing_cost_per_box

    # 8. 총 비용 계산 (수량 및 기타 비용 적용)
    total_cost = cost_per_box_before_print * qty
    total_cost += print_cost_map.get(print_color, 0) # 인쇄비는 총액으로 더함

    if vat:
        total_cost *= 1.1

    # 최종 단가
    unit_price = round(total_cost / qty if qty else 0, 2)

    # 상세 내역
    detail = {
        "장(mm)": 장, "폭(mm)": 폭, "고(mm)": 고,
        "전장(mm)": 전장, "전폭(mm)": 전폭, "폭수": 폭수,
        "계산된 실제지폭(mm)": 실제지폭,
        "박스당 소요량(㎡)": round(area_per_box, 5),
        "적용 로스율(%)": loss_rate,
        "㎡당 원재료비(원, 로스포함)": round(material_cost_per_sqm, 2),
        "박스당 원단비(원)": round(material_cost_per_box, 2),
        "박스당 가공비(원)": round(processing_cost_per_box, 2),
        "수량": qty,
        "부가세 포함": "예" if vat else "아니오",
        "총 비용 (VAT포함)": round(total_cost, 2),
        "개당 최종 단가(원)": unit_price,
    }
    return unit_price, detail


# --- Streamlit 앱 UI 구성 ---
st.set_page_config(layout="wide")
st.title("TOVIX 박스 제작 단가 계산기 (v2.0)")
st.caption("IT운영팀 (로스율 적용)")

# --- 사이드바: 원지 데이터 관리 ---
with st.sidebar:
    st.header("📄 원지 데이터 관리")
    st.caption("제조사별 원지값(원/kg)과 평량(g/㎡)을 입력하세요.")

    paper_data = {}
    # 수정된 기본 데이터를 UI에 반영
    for paper, values in paper_data_default.items():
        st.markdown(f"**{paper}**")
        col1, col2 = st.columns(2)
        price = col1.number_input(f"원지값(원/kg)", value=values["원지값"], key=f"price_{paper}")
        grammage = col2.number_input(f"평량(g/㎡)", value=values["평량"], key=f"gram_{paper}")
        paper_data[paper] = {"원지값": price, "평량": grammage}

# --- 메인 화면: 입력 및 결과 ---
col_main1, col_main2 = st.columns([1, 1.2])

with col_main1:
    st.subheader("1️⃣ 박스 사양 입력")

    c1, c2, c3 = st.columns(3)
    장 = c1.number_input("장(L, mm)", value=300)
    폭 = c2.number_input("폭(W, mm)", value=200)
    고 = c3.number_input("고(H, mm)", value=150)

    c4, c5, c6 = st.columns(3)
    미미 = c4.number_input("미미(접착여유, mm)", value=40)
    폭수 = c5.number_input("폭수", min_value=1, value=4)
    여유값 = c6.number_input("재단 여유값(mm)", value=50)

    st.markdown("---")
    st.subheader("2️⃣ 원단 및 공정 선택")

    flute_grade = st.radio("골 종류", list(corrugated_factor_map.keys()), index=3, horizontal=True)

    board_spec = {}
    paper_keys = list(paper_data.keys())

    if "DW" in flute_grade:
        st.info("DW골(이중골) 사양을 선택하세요.")
        board_spec['표면지'] = st.selectbox("표면지", paper_keys, index=4)
        board_spec['골심지A'] = st.selectbox("골심지A", paper_keys, index=0)
        board_spec['중심지'] = st.selectbox("중심지", paper_keys, index=0)
        board_spec['골심지B'] = st.selectbox("골심지B", paper_keys, index=0)
        board_spec['이면지'] = st.selectbox("이면지", paper_keys, index=2)
    else:
        st.info("편면골 사양을 선택하세요.")
        board_spec['표면지'] = st.selectbox("표면지", paper_keys, index=4)
        board_spec['골심지'] = st.selectbox("골심지", paper_keys, index=0)
        board_spec['이면지'] = st.selectbox("이면지", paper_keys, index=2)

    st.markdown("---")
    st.subheader("3️⃣ 비용 및 수량 입력")

    print_color = st.selectbox("인쇄 도수 (총 비용)", list(print_cost_map.keys()), index=1)

    # --- [핵심 수정] 로스율 입력 필드 추가 ---
    loss_rate = st.number_input("재료 로스율(%)", min_value=0.0, value=10.0, step=0.1, format="%.1f",
                                help="원단 재단 및 가공 시 발생하는 손실률입니다. (예: 10% -> 10)")

    c7, c8, c9 = st.columns(3)
    die_cut_unit = c7.number_input("톰슨비(도무송, 1개당)", value=50)
    glue_unit = c8.number_input("접착비(1개당)", value=30)
    extra_unit = c9.number_input("부자재비(1개당)", value=0)

    qty = st.number_input("총 생산 수량", min_value=1, value=1000)
    vat = st.checkbox("부가세 10% 포함", value=True)

with col_main2:
    st.subheader("✨ 계산 결과")
    if st.button("단가 계산 실행"):
        unit_price, detail = calculate_price_new(
            장, 폭, 고, 미미, 폭수, 여유값,
            board_spec, paper_data,
            flute_grade, print_color,
            die_cut_unit, glue_unit, extra_unit, loss_rate, qty, vat # loss_rate 전달
        )

        if unit_price is None:
            st.error(detail["오류"])
        else:
            st.metric("▶ 개당 예상 단가 (원)", f"{unit_price:,.2f}")

            st.markdown("### 상세 내역")
            # 컬럼 순서를 원하는 대로 조정하기 위해 리스트에서 DataFrame 생성
            detail_df_data = {
                "항목": list(detail.keys()),
                "값": list(detail.values())
            }
            df_detail = pd.DataFrame(detail_df_data)
            st.dataframe(df_detail)

            # 엑셀 저장
            def to_excel(df):
                output = BytesIO()
                # with문을 사용하여 writer를 안전하게 닫음
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='견적서')
                return output.getvalue()

            df_for_excel = pd.DataFrame([detail])
            excel_data = to_excel(df_for_excel)

            st.download_button(
                label="상세내역 엑셀로 저장",
                data=excel_data,
                file_name=f"box_price_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )