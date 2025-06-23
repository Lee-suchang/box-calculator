import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime
import math

# --- [핵심] 업체별 데이터 구조 정의 ---
paper_data_A = {
    "S120": {"원지값": 580, "평량": 120}, "B150": {"원지값": 560, "평량": 150},
    "K180": {"원지값": 560, "평량": 180}, "K200": {"원지값": 630, "평량": 180},
    "SK180": {"원지값": 650, "평량": 180}, "KLB175": {"원지값": 720, "평량": 175},
    "WK180": {"원지값": 850, "평량": 180}
}
paper_data_B = {
    "S120": {"원지값": 590, "평량": 120}, "B150": {"원지값": 570, "평량": 150},
    "K180": {"원지값": 660, "평량": 180}, "K200": {"원지값": 640, "평량": 200},
    "SK180": {"원지값": 660, "평량": 180}, "KLB175": {"원지값": 730, "평량": 175},
    "WK180": {"원지값": 860, "평량": 180}
}
paper_data_C = {
    "S120": {"원지값": 575, "평량": 120}, "B150": {"원지값": 555, "평량": 150},
    "K180": {"원지값": 645, "평량": 180}, "K200": {"원지값": 625, "평량": 200},
    "SK180": {"원지값": 645, "평량": 180}, "KLB175": {"원지값": 715, "평량": 175},
    "WK180": {"원지값": 845, "평량": 180}
}
supplier_data = {
    "업체 A": paper_data_A, "업체 B": paper_data_B, "업체 C": paper_data_C,
}

corrugated_factor_map = {
    "E골": 1.3, "B골": 1.4, "A골": 1.6, "DW골(A+B)": 1.6 + 1.4
}
processing_cost_per_sqm_map = {
    "E골": 15, "B골": 10, "A골": 20, "DW골(A+B)": 29
}

# --- 계산 함수 (엑셀 IF 로직 최종 적용) ---
def calculate_definitive_cost_v13(
        장, 폭, 고, 미미, 여유값, 폭수,
        board_spec, paper_data,
        flute_grade, loss_rate
):
    전장 = (장 + 폭) * 2 + 미미
    전폭 = 폭 + 고

    실제지폭 = (전폭 * 폭수) + 여유값

    # 엑셀의 복잡한 IF 로직을 그대로 코드로 구현
    if 실제지폭 > 2500: 생산지폭 = 2500 # 최대값 처리, 혹은 오류 반환 가능
    elif 실제지폭 >= 2400: 생산지폭 = 2500
    elif 실제지폭 >= 2300: 생산지폭 = 2400
    elif 실제지폭 >= 2200: 생산지폭 = 2300
    elif 실제지폭 >= 2100: 생산지폭 = 2200
    elif 실제지폭 >= 2000: 생산지폭 = 2100
    elif 실제지폭 >= 1900: 생산지폭 = 2000
    elif 실제지폭 >= 1800: 생산지폭 = 1900
    elif 실제지폭 >= 1750: 생산지폭 = 1800
    elif 실제지폭 >= 1700: 생산지폭 = 1750
    elif 실제지폭 >= 1650: 생산지폭 = 1700
    elif 실제지폭 >= 1600: 생산지폭 = 1650
    elif 실제지폭 >= 1550: 생산지폭 = 1600
    elif 실제지폭 >= 1500: 생산지폭 = 1550
    elif 실제지폭 >= 1450: 생산지폭 = 1500
    elif 실제지폭 >= 1400: 생산지폭 = 1450
    elif 실제지폭 >= 1350: 생산지폭 = 1400
    elif 실제지폭 >= 1300: 생산지폭 = 1350
    elif 실제지폭 >= 1250: 생산지폭 = 1300
    elif 실제지폭 >= 1200: 생산지폭 = 1250
    elif 실제지폭 >= 1150: 생산지폭 = 1200
    elif 실제지폭 >= 1100: 생산지폭 = 1150
    else: 생산지폭 = 실제지폭

    if 폭수 > 0: area_per_box = (전장 * 생산지폭) / 폭수 / 1_000_000
    else: area_per_box = 0

    material_cost_per_sqm_base = 0
    layers = []
    if "DW" in flute_grade: layers.extend(['표면지', '골심지A', '중심지', '골심지B', '이면지'])
    else: layers.extend(['표면지', '골심지', '이면지'])

    for layer_name in layers:
        paper_type = board_spec.get(layer_name)
        if paper_type and paper_type in paper_data:
            price_kg = paper_data[paper_type]['원지값']
            grammage_kg = paper_data[paper_type]['평량'] / 1000
            factor = 1.0
            if '골심지A' in layer_name: factor = 1.6
            elif '골심지B' in layer_name: factor = 1.4
            elif '골심지' in layer_name: factor = corrugated_factor_map.get(flute_grade, 1.4)
            material_cost_per_sqm_base += price_kg * grammage_kg * factor

    material_cost_per_sqm_unrounded = material_cost_per_sqm_base * (1 + (loss_rate / 100))
    rounded_material_cost_per_sqm = int(round(material_cost_per_sqm_unrounded))
    sqm_processing_cost = processing_cost_per_sqm_map.get(flute_grade, 0)
    total_cost_per_sqm = rounded_material_cost_per_sqm + sqm_processing_cost
    final_base_cost = total_cost_per_sqm * area_per_box

    detail = {
        "입력: 장(mm)": 장, "입력: 폭(mm)": 폭, "입력: 고(mm)": 고,
        "입력: 미미(mm)": 미미, "입력: 여유값(mm)": 여유값, "입력: 폭수": 폭수,
        "계산: 전장(mm)": 전장, "계산: 전폭(mm)": 전폭,
        "계산: 실제지폭(mm)": 실제지폭, # 용어 변경
        "계산: 최종 생산지폭(mm)": 생산지폭,
        "계산: 박스당 소요량(㎡)": round(area_per_box, 6),
        "㎡당 원재료비(반올림)": rounded_material_cost_per_sqm,
        "㎡당 가공비(자동적용)": sqm_processing_cost,
        "㎡당 총단가 (A)": total_cost_per_sqm,
        "개당 최종 원가 (A*B)": round(final_base_cost, 6),
    }
    return final_base_cost, detail

# --- Streamlit 앱 UI 구성 ---
st.set_page_config(layout="wide")
st.title("TOVIX 박스 기본 원가 계산기 (v13.0)")
st.caption("IT운영팀 (업체관리/최종로직)")

with st.sidebar:
    st.header("📄 원지 데이터 관리")
    selected_supplier = st.radio("업체 선택", options=list(supplier_data.keys()), horizontal=True)
    active_paper_data_defaults = supplier_data[selected_supplier]
    st.markdown("---")

    paper_data = {}
    for paper, values in active_paper_data_defaults.items():
        st.markdown(f"**{paper}**")
        col1, col2 = st.columns(2)
        key_suffix = f"_{selected_supplier}_{paper}"
        price = col1.number_input(f"원지값(원/kg)", value=values["원지값"], key=f"price{key_suffix}")
        grammage = col2.number_input(f"평량(g/㎡)", value=values["평량"], key=f"gram{key_suffix}")
        paper_data[paper] = {"원지값": price, "평량": grammage}

col_main1, col_main2 = st.columns([1, 1.2])

with col_main1:
    st.subheader("1️⃣ 박스 사양 입력")
    c1, c2, c3 = st.columns(3)
    장 = c1.number_input("장(L, mm)", value=350)
    폭 = c2.number_input("폭(W, mm)", value=300)
    고 = c3.number_input("고(H, mm)", value=390)

    st.subheader("2️⃣ 생산 사양 입력")
    c4, c5, c6 = st.columns(3)
    미미 = c4.number_input("미미(mm)", value=35)
    여유값 = c5.number_input("재단 여유값(mm)", value=20, help="엑셀 예시의 실제지폭 1400에 맞춘 기본값")
    폭수 = c6.number_input("폭수", min_value=1, value=2)

    st.markdown("---")
    st.subheader("3️⃣ 원단 및 공정 선택")
    flute_grade = st.radio("골 종류", list(corrugated_factor_map.keys()), index=3, horizontal=True)
    loss_rate = st.number_input("재료 로스율(%)", min_value=0.0, value=10.0, step=0.1, format="%.1f")

    board_spec = {}
    paper_keys = list(paper_data.keys())
    if "DW" in flute_grade:
        st.info("DW골(이중골) 사양을 선택하세요.")
        board_spec['표면지'] = st.selectbox("표면지", paper_keys, index=4, key=f'dw_outer_{selected_supplier}')
        board_spec['골심지A'] = st.selectbox("골심지A", paper_keys, index=0, key=f'dw_flute_a_{selected_supplier}')
        board_spec['중심지'] = st.selectbox("중심지", paper_keys, index=0, key=f'dw_center_{selected_supplier}')
        board_spec['골심지B'] = st.selectbox("골심지B", paper_keys, index=0, key=f'dw_flute_b_{selected_supplier}')
        board_spec['이면지'] = st.selectbox("이면지", paper_keys, index=2, key=f'dw_inner_{selected_supplier}')
    else:
        st.info("편면골 사양을 선택하세요.")
        board_spec['표면지'] = st.selectbox("표면지", paper_keys, index=4, key=f'single_outer_{selected_supplier}')
        board_spec['골심지'] = st.selectbox("골심지", paper_keys, index=0, key=f'single_flute_{selected_supplier}')
        board_spec['이면지'] = st.selectbox("이면지", paper_keys, index=2, key=f'single_inner_{selected_supplier}')

with col_main2:
    st.subheader("✨ 계산 결과")
    if st.button("기본 원가 계산"):
        base_cost, detail = calculate_definitive_cost_v13(
            장, 폭, 고, 미미, 여유값, 폭수,
            board_spec, paper_data,
            flute_grade, loss_rate
        )

        if base_cost is None:
            st.error(detail.get("오류", "알 수 없는 오류 발생"))
        else:
            st.metric("▶ 개당 최종 원가 (원)", f"{base_cost:,.6f}")
            st.markdown("### 상세 내역 (모든 계산 과정)")
            df_detail = pd.DataFrame(detail.items(), columns=["항목", "값"])
            st.dataframe(df_detail)

            def to_excel(df):
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='원가계산서')
                return output.getvalue()
            df_for_excel = pd.DataFrame([detail])
            excel_data = to_excel(df_for_excel)
            st.download_button(
                label="상세내역 엑셀로 저장",
                data=excel_data,
                file_name=f"box_cost_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
