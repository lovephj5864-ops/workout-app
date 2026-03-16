import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import copy
import pandas as pd
import math
import json
import os

# ==========================================
# ⭐ 강력한 해결책: 사이드바 수동 동기화 버튼
# ==========================================
with st.sidebar:
    st.subheader("🔄 서버 데이터 동기화")
    st.caption("구글 시트와 연결이 끊기거나 데이터가 안 보일 때 눌러주세요. (캐시 초기화)")
    if st.button("앱 초기화 및 새로고침", type="primary", use_container_width=True):
        st.cache_data.clear()       # 10분 기억 지우기
        st.cache_resource.clear()   # 구글 연결 초기화
        st.session_state.clear()    # 화면 상태 초기화
        st.success("초기화 완료! 데이터를 다시 불러옵니다.")
        st.rerun()

# ----------------------------------------------------
# 0. 구글 시트 연결
# ----------------------------------------------------
@st.cache_resource(ttl=3000)
def init_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    if os.path.exists("secrets.json"):
        creds = ServiceAccountCredentials.from_json_keyfile_name("secrets.json", scope)
    else:
        creds_dict = json.loads(st.secrets["gcp_service_account"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open("운동기록_DB")

doc = init_connection()

# ----------------------------------------------------
# 1. DB 데이터 불러오기/저장하기 함수 (안정성 극대화)
# ----------------------------------------------------
@st.cache_data(ttl=60)
def get_past_logs():
    try:
        logs_sheet = doc.worksheet("Logs")
        records = logs_sheet.get_all_records()
        if not records: return pd.DataFrame()
        return pd.DataFrame(records)
    except Exception:
        return pd.DataFrame()

@st.cache_data(ttl=600)
def load_exercises_from_sheet():
    try:
        ex_sheet = doc.worksheet("Exercises")
        # get_all_records 대신 get_all_values를 써서 빈칸/에러로 인한 튕김 방지!
        all_data = ex_sheet.get_all_values() 
        ex_dict = {"가슴": [], "등": [], "하체": [], "어깨": [], "팔": [], "복근/코어": [], "유산소": []}
        if len(all_data) > 1:
            for row in all_data[1:]:
                if len(row) >= 2:
                    part = str(row[0]).strip()
                    name = str(row[1]).strip()
                    if part in ex_dict and name:
                        ex_dict[part].append(name)
        return ex_dict
    except Exception as e:
        print(f"종목 로드 에러: {e}")
        return None

@st.cache_data(ttl=600)
def load_routines_from_sheet():
    try:
        routine_sheet = doc.worksheet("Routines")
        all_data = routine_sheet.get_all_values()
        r_dict = {}
        if len(all_data) > 1:
            for row in all_data[1:]:
                if len(row) >= 2:
                    name = str(row[0]).strip()
                    data_str = str(row[1]).strip()
                    if name and data_str:
                        r_dict[name] = json.loads(data_str)
        return r_dict
    except Exception as e:
        print(f"루틴 로드 에러: {e}")
        return None

def save_routine_to_sheet(routine_name, routine_data):
    try:
        routine_sheet = doc.worksheet("Routines")
        data_str = json.dumps(routine_data, ensure_ascii=False)
        names_in_sheet = routine_sheet.col_values(1)
        
        if routine_name in names_in_sheet:
            row_idx = names_in_sheet.index(routine_name) + 1
            routine_sheet.update_cell(row_idx, 2, data_str)
        else:
            routine_sheet.append_row([routine_name, data_str])
            
        # 저장 후 화면 동기화
        st.session_state.routines[routine_name] = routine_data
        load_routines_from_sheet.clear() 
        
        if st.session_state.get('active_routine_name') == routine_name:
            st.session_state.active_workout = copy.deepcopy(routine_data)
            
        return True
    except Exception as e:
        st.error(f"구글 시트 저장 실패! 1분 뒤 사이드바의 [새로고침]을 누르고 다시 시도하세요. (에러: {e})")
        return False

# ----------------------------------------------------
# 2. 매드프로페서 중량 계산 함수
# ----------------------------------------------------
def round_to_plate(weight, min_plate):
    step = min_plate * 2
    return round(weight / step) * step

def calculate_madprofessor_start_weight(pr_weight, pr_reps, min_plate):
    if pr_weight == 0 or pr_reps == 0: return 0
    one_rm = pr_weight * (1 + 0.0333 * pr_reps)
    five_rm = one_rm * 0.8888
    start_weight = five_rm * 0.925
    return round_to_plate(start_weight, min_plate)

# ----------------------------------------------------
# 3. 앱 세션 초기화 (에러 감지 및 복구 기능 포함)
# ----------------------------------------------------
if 'exercises' not in st.session_state or st.session_state.exercises is None:
    loaded_ex = load_exercises_from_sheet()
    if loaded_ex:
        st.session_state.exercises = loaded_ex
    else:
        # 에러 시 나타나는 비상용 데이터
        st.session_state.exercises = {"가슴": ["플랫 벤치프레스"], "등": ["데드리프트"], "하체": ["바벨 스쿼트"], "어깨": [], "팔": [], "복근/코어": [], "유산소": []}

if 'routines' not in st.session_state or st.session_state.routines is None:
    loaded_r = load_routines_from_sheet()
    if loaded_r is not None:
        st.session_state.routines = loaded_r
    else:
        st.session_state.routines = {}

def get_flat_exercise_list():
    flat_list = []
    for category, ex_list in st.session_state.exercises.items():
        for ex in ex_list:
            flat_list.append(f"[{category}] {ex}")
    return flat_list

# ----------------------------------------------------
# 화면 UI 시작
# ----------------------------------------------------
st.title("🏋️ 플릭 스타일 운동 트래커")
current_user = st.text_input("👤 사용자 닉네임 입력 (개인 맞춤 증량을 위해 필수)", placeholder="예: 운동매니아1")

tab_workout, tab_manage, tab_mad = st.tabs(["💪 오늘의 운동", "⚙️ 종목 및 루틴 관리", "🔥 매드프로페서 5x5"])
past_logs_df = get_past_logs()

# ==========================================
# [탭 3] 매드프로페서 5x5
# ==========================================
with tab_mad:
    st.header("매드프로페서 5x5 자동 루틴 생성")
    col_plate, col_blank = st.columns(2)
    min_plate = col_plate.selectbox("가장 가벼운 원판 (kg)", [1.25, 2.5, 5.0], index=0)
    
    c1, c2, c3 = st.columns(3)
    with c1:
        sq_w = st.number_input("스쿼트 무게", value=100.0, step=2.5, key="sq_w")
        sq_r = st.number_input("스쿼트 횟수", value=5, step=1, key="sq_r")
    with c2:
        bp_w = st.number_input("벤치 무게", value=70.0, step=2.5, key="bp_w")
        bp_r = st.number_input("벤치 횟수", value=5, step=1, key="bp_r")
    with c3:
        dl_w = st.number_input("데드 무게", value=120.0, step=2.5, key="dl_w")
        dl_r = st.number_input("데드 횟수", value=5, step=1, key="dl_r")
        
    if st.button("🚀 매드프로페서 1주차 루틴 생성 & 전체 공유", type="primary", use_container_width=True):
        sq_start = calculate_madprofessor_start_weight(sq_w, sq_r, min_plate)
        bp_start = calculate_madprofessor_start_weight(bp_w, bp_r, min_plate)
        dl_start = calculate_madprofessor_start_weight(dl_w, dl_r, min_plate)
        
        mad_routine = [
            {"name": "바벨 스쿼트", "target_sets": 5, "target_reps": 5, "suggested_weight": sq_start},
            {"name": "플랫 벤치프레스", "target_sets": 5, "target_reps": 5, "suggested_weight": bp_start},
            {"name": "바벨 로우", "target_sets": 5, "target_reps": 5, "suggested_weight": bp_start * 0.8}
        ]
        routine_name = f"[매드프로페서] 1주차 월요일 ({current_user if current_user else '기본'})"
        
        if save_routine_to_sheet(routine_name, mad_routine):
            st.success(f"루틴 생성 완료! 이제 모든 사용자가 이 루틴을 볼 수 있습니다.")

# ==========================================
# [탭 2] 종목 및 루틴 관리
# ==========================================
with tab_manage:
    st.header("1. 종목 관리 (추가 및 삭제)")
    manage_col1, manage_col2 = st.columns(2)
    
    with manage_col1:
        st.subheader("➕ 종목 추가")
        add_category = st.selectbox("부위 선택", list(st.session_state.exercises.keys()), key="add_cat")
        new_exercise = st.text_input("추가할 운동 이름", placeholder="예: 스모 데드리프트")
        if st.button("종목 추가하기", use_container_width=True):
            if new_exercise and new_exercise not in st.session_state.exercises[add_category]:
                st.session_state.exercises[add_category].append(new_exercise)
                try:
                    ex_sheet = doc.worksheet("Exercises")
                    ex_sheet.append_row([add_category, new_exercise])
                    load_exercises_from_sheet.clear()
                    st.success(f"[{add_category}] '{new_exercise}' 추가 완료!")
                except Exception as e:
                    st.error("구글 시트 저장 실패")
                st.rerun()
                
    with manage_col2:
        st.subheader("➖ 종목 삭제")
        del_category = st.selectbox("부위 선택", list(st.session_state.exercises.keys()), key="del_cat")
        if st.session_state.exercises[del_category]:
            del_exercise = st.selectbox("삭제할 운동 선택", st.session_state.exercises[del_category], key="del_ex")
            if st.button("종목 삭제하기", type="secondary", use_container_width=True):
                st.session_state.exercises[del_category].remove(del_exercise)
                try:
                    ex_sheet = doc.worksheet("Exercises")
                    all_data = ex_sheet.get_all_values()
                    row_to_delete = None
                    for i, row in enumerate(all_data):
                        if len(row) >= 2 and row[0] == del_category and row[1] == del_exercise:
                            row_to_delete = i + 1
                            break
                    if row_to_delete:
                        ex_sheet.delete_rows(row_to_delete)
                        load_exercises_from_sheet.clear()
                        st.success(f"'{del_exercise}' 삭제 완료!")
                except Exception as e:
                    st.error(f"구글 시트 삭제 중 오류 발생: {e}")
                st.rerun()
        else:
            st.caption("해당 부위에 등록된 종목이 없습니다.")

    st.write("")
    st.subheader("📋 부위별 등록된 종목 목록 (DB 연동)")
    cols = st.columns(3)
    col_idx = 0
    for category, ex_list in st.session_state.exercises.items():
        with cols[col_idx % 3].expander(f"**{category}** ({len(ex_list)}개)"):
            for ex in ex_list:
                st.write(f"- {ex}")
        col_idx += 1

    st.divider()

    st.header("2. 새 루틴 만들기 (공유됨)")
    new_routine_name = st.text_input("새 루틴 이름", placeholder="예: 월요일 가슴/삼두 루틴")
    
    filter_categories = st.multiselect("부위 필터링", list(st.session_state.exercises.keys()))
    filtered_flat_exercise_list = []
    for category, ex_list in st.session_state.exercises.items():
        if not filter_categories or category in filter_categories:
            for ex in ex_list:
                filtered_flat_exercise_list.append(f"[{category}] {ex}")
                
    selected_exs = st.multiselect("이 루틴에 포함할 운동을 순서대로 고르세요", filtered_flat_exercise_list)
    
    routine_details = []
    if selected_exs:
        for ex in selected_exs:
            c1, c2, c3 = st.columns([2, 1, 1])
            clean_name = ex.split("] ")[1] if "] " in ex else ex
            c1.markdown(f"**{clean_name}**")
            sets = c2.number_input(f"세트", min_value=1, value=4, key=f"set_{ex}", label_visibility="collapsed")
            reps = c3.number_input(f"횟수", min_value=1, value=10, key=f"rep_{ex}", label_visibility="collapsed")
            routine_details.append({"name": clean_name, "target_sets": sets, "target_reps": reps})
            
    if st.button("💾 새 루틴 저장 및 공유하기", type="primary", use_container_width=True):
        if new_routine_name and routine_details:
            if save_routine_to_sheet(new_routine_name, routine_details):
                st.success(f"'{new_routine_name}' 루틴이 DB에 저장되어 모두에게 공유되었습니다!")

    st.write("---")

    st.header("3. 내 루틴 편집 (순서 변경 및 세부조절)")
    if not st.session_state.routines:
        st.info("등록된 루틴이 없습니다.")
    else:
        edit_routine_name = st.selectbox("편집할 루틴을 선택하세요", list(st.session_state.routines.keys()))
        routine_to_edit = st.session_state.routines[edit_routine_name]
        
        for i, workout in enumerate(routine_to_edit):
            st.markdown(f"**{i + 1}. {workout['name']}**")
            c_up, c_dn, c_del, c_exp = st.columns([1, 1, 1, 6])
            
            with c_up:
                if st.button("⬆️", key=f"up_{edit_routine_name}_{i}"):
                    if i > 0:
                        routine_to_edit[i], routine_to_edit[i-1] = routine_to_edit[i-1], routine_to_edit[i]
                        save_routine_to_sheet(edit_routine_name, routine_to_edit)
                        st.rerun()
            with c_dn:
                if st.button("⬇️", key=f"dn_{edit_routine_name}_{i}"):
                    if i < len(routine_to_edit) - 1:
                        routine_to_edit[i], routine_to_edit[i+1] = routine_to_edit[i+1], routine_to_edit[i]
                        save_routine_to_sheet(edit_routine_name, routine_to_edit)
                        st.rerun()
            with c_del:
                if st.button("❌", key=f"del_{edit_routine_name}_{i}"):
                    routine_to_edit.pop(i)
                    save_routine_to_sheet(edit_routine_name, routine_to_edit)
                    st.rerun()
                    
            with c_exp:
                with st.expander("세트/횟수 세부 설정", expanded=False):
                    ec1, ec2 = st.columns(2)
                    new_sets = ec1.number_input("목표 세트수", min_value=1, value=workout['target_sets'], key=f"esets_{edit_routine_name}_{i}")
                    new_reps = ec2.number_input("목표 횟수", min_value=1, value=workout['target_reps'], key=f"ereps_{edit_routine_name}_{i}")
                    if new_sets != workout['target_sets'] or new_reps != workout['target_reps']:
                        workout['target_sets'] = new_sets
                        workout['target_reps'] = new_reps
                        if st.button("세부 설정 적용", key=f"apply_{edit_routine_name}_{i}"):
                            save_routine_to_sheet(edit_routine_name, routine_to_edit)
                            st.success("적용됨")

        if st.button("🗑️ 이 루틴 전체 삭제", type="secondary", key=f"del_all_{edit_routine_name}"):
            del st.session_state.routines[edit_routine_name]
            try:
                sheet = doc.worksheet("Routines")
                names_in_sheet = sheet.col_values(1)
                if edit_routine_name in names_in_sheet:
                    row_idx = names_in_sheet.index(edit_routine_name) + 1
                    sheet.delete_rows(row_idx)
            except Exception as e: pass
            
            load_routines_from_sheet.clear()
            if st.session_state.get('active_routine_name') == edit_routine_name:
                del st.session_state['active_routine_name']
            st.rerun()

# ==========================================
# [탭 1] 오늘의 운동 기록 화면
# ==========================================
with tab_workout:
    if not current_user:
        st.warning("⚠️ 상단에 [사용자 닉네임]을 입력하셔야 루틴을 시작하고 개인 기록을 불러올 수 있습니다.")
    elif not st.session_state.routines:
        st.warning("등록된 공유 루틴이 없습니다. [종목 및 루틴 관리] 탭에서 루틴을 먼저 만들어주세요!")
    else:
        selected_routine_name = st.selectbox("루틴 목록 (모든 사용자 공유)", list(st.session_state.routines.keys()), label_visibility="collapsed")
        
        if 'active_routine_name' not in st.session_state or st.session_state.active_routine_name != selected_routine_name:
            st.session_state.active_routine_name = selected_routine_name
            st.session_state.active_workout = copy.deepcopy(st.session_state.routines[selected_routine_name])
            for key in list(st.session_state.keys()):
                if key.startswith("done_"):
                    del st.session_state[key]

        today_logs = []

        if 'active_workout' in st.session_state:
            for w_idx, workout in enumerate(st.session_state.active_workout):
                with st.expander(f"🔥 {workout['name']}", expanded=True):
                    
                    ctrl1, ctrl2, ctrl3 = st.columns(3)
                    if ctrl1.button("➕ 1세트 추가", key=f"add_{w_idx}"):
                        workout['target_sets'] += 1
                        st.rerun()
                    if ctrl2.button("➖ 1세트 삭제", key=f"sub_{w_idx}") and workout['target_sets'] > 1:
                        workout['target_sets'] -= 1
                        st.rerun()
                    if ctrl3.button("✅ 일괄 완료", key=f"all_{w_idx}"):
                        for i in range(1, workout['target_sets'] + 1):
                            st.session_state[f"done_{w_idx}_{i}"] = True
                        st.rerun()

                    st.write("") 

                    default_w = workout.get('suggested_weight', 20.0)
                    default_r = workout['target_reps']
                    sets = workout['target_sets']
                    ex_name = workout['name']
                    
                    past_msg = ""
                    can_increase = False
                    last_weight = default_w
                    
                    if not past_logs_df.empty and '사용자' in past_logs_df.columns:
                        past_data = past_logs_df[(past_logs_df['종목'] == ex_name) & (past_logs_df['사용자'] == current_user)]
                        if not past_data.empty:
                            last_date = past_data['날짜'].max()
                            last_session = past_data[past_data['날짜'] == last_date]
                            
                            success_count = len(last_session[last_session['완료여부'] == 'O'])
                            total_count = len(last_session)
                            last_weight = float(last_session['무게'].iloc[-1])
                            last_reps = int(last_session['횟수'].iloc[-1])
                            
                            past_msg = f"📅 **{current_user}**님의 마지막 기록({last_date}): **{last_weight}kg x {last_reps}회 x {total_count}세트** "
                            
                            if success_count == total_count and total_count > 0:
                                past_msg += "(전 세트 성공! 🌟)"
                                can_increase = True
                            else:
                                past_msg += f"({success_count}/{total_count} 세트 완료)"
                    
                    if can_increase:
                        st.success(past_msg)
                        decision = st.radio(
                            "오늘의 증량 여부를 선택하세요!", 
                            [f"유지하기 ({last_weight}kg)", f"2.5kg 증량하기 ({last_weight + 2.5}kg)"], 
                            horizontal=True, key=f"dec_{w_idx}"
                        )
                        master_weight = last_weight + 2.5 if "증량하기" in decision else last_weight
                    elif past_msg:
                        st.info(past_msg + " ➔ 오늘은 동일한 무게로 완벽한 자세에 도전해보세요!")
                        master_weight = last_weight
                    else:
                        master_weight = default_w

                    st.write("") 
                    input_mode = st.radio("입력 모드 선택", ["전체 세트 일괄 설정", "세트별 개별 설정"], horizontal=True, key=f"mode_{w_idx}", label_visibility="collapsed")
                    
                    if input_mode == "전체 세트 일괄 설정":
                        mc1, mc2 = st.columns(2)
                        master_weight = mc1.number_input(f"일괄 목표 무게(kg)", value=float(master_weight), step=2.5, key=f"mw_{w_idx}")
                        master_reps = mc2.number_input(f"일괄 목표 횟수", value=default_r, step=1, key=f"mr_{w_idx}")

                    cols = st.columns([1, 2, 2, 1])
                    cols[0].write("세트")
                    cols[1].write("무게")
                    cols[2].write("횟수")
                    cols[3].write("완료")

                    for i in range(1, sets + 1):
                        c1, c2, c3, c4 = st.columns([1, 2, 2, 1])
                        c1.write(f"**{i}**")
                        
                        if input_mode == "전체 세트 일괄 설정":
                            c2.markdown(f"<div style='padding-top:8px;'>{master_weight} kg</div>", unsafe_allow_html=True)
                            c3.markdown(f"<div style='padding-top:8px;'>{master_reps} 회</div>", unsafe_allow_html=True)
                            weight_val = master_weight
                            reps_val = master_reps
                        else:
                            weight_val = c2.number_input("무게", value=float(master_weight), step=2.5, key=f"w_{w_idx}_{i}", label_visibility="collapsed")
                            reps_val = c3.number_input("횟수", value=default_r, step=1, key=f"r_{w_idx}_{i}", label_visibility="collapsed")
                        
                        done_val = c4.checkbox("완료", key=f"done_{w_idx}_{i}", label_visibility="collapsed")

                        today_logs.append([
                            datetime.now().strftime("%Y-%m-%d"),
                            current_user,
                            selected_routine_name,
                            ex_name,
                            i,
                            weight_val,
                            reps_val,
                            "O" if done_val else "X"
                        ])

            st.divider()
            if st.button("🚀 오늘 운동 결과 최종 저장하기", type="primary", use_container_width=True):
                with st.spinner('구글 시트에 기록을 저장하는 중입니다...'):
                    try:
                        logs_sheet = doc.worksheet("Logs")
                        logs_sheet.append_rows(today_logs)
                        st.success("🎉 구글 시트(Logs)에 데이터가 완벽하게 저장되었습니다!")
                        get_past_logs.clear() # 운동 기록 저장 후 로그 캐시 초기화
                        st.balloons()
                    except Exception as e:
                        st.error(f"저장 중 오류가 발생했습니다. (에러: {e})")
