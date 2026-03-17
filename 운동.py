import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import copy
import pandas as pd
import math
import json
import os
import time  # 타이머용 추가
import streamlit.components.v1 as components # 부드러운 UI 시계용 추가

# ==========================================
# ⭐ 사이드바 수동 동기화 버튼
# ==========================================
with st.sidebar:
    st.subheader("🔄 서버 데이터 동기화")
    st.caption("구글 시트와 연결이 끊기거나 데이터가 안 보일 때 눌러주세요. (캐시 초기화)")
    if st.button("앱 초기화 및 새로고침", type="primary", use_container_width=True):
        st.cache_data.clear()       
        st.cache_resource.clear()   
        st.session_state.clear()    
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
# 1. DB 데이터 불러오기/저장하기 함수
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
            
        st.session_state.routines[routine_name] = routine_data
        load_routines_from_sheet.clear() 
        
        if st.session_state.get('active_routine_name') == routine_name:
            st.session_state.active_workout = copy.deepcopy(routine_data)
            
        return True
    except Exception as e:
        st.error(f"구글 시트 저장 실패! 1분 뒤 사이드바의 [새로고침]을 누르고 다시 시도하세요.")
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
# 3. 앱 세션 초기화
# ----------------------------------------------------
if 'exercises' not in st.session_state or st.session_state.exercises is None:
    loaded_ex = load_exercises_from_sheet()
    if loaded_ex:
        st.session_state.exercises = loaded_ex
    else:
        st.session_state.exercises = {"가슴": ["플랫 벤치프레스"], "등": ["데드리프트"], "하체": ["바벨 스쿼트"], "어깨": [], "팔": [], "복근/코어": [], "유산소": []}

if 'routines' not in st.session_state or st.session_state.routines is None:
    loaded_r = load_routines_from_sheet()
    if loaded_r is not None:
        st.session_state.routines = loaded_r
    else:
        st.session_state.routines = {}

# ----------------------------------------------------
# 화면 UI 시작
# ----------------------------------------------------
st.title("🏋️ 플릭 스타일 운동 트래커")
current_user = st.text_input("👤 사용자 닉네임 입력 (개인 맞춤 증량을 위해 필수)", placeholder="예: 운동매니아1")

tab_workout, tab_manage, tab_mad, tab_analysis = st.tabs(["💪 오늘의 운동", "⚙️ 종목 및 루틴 관리", "🔥 매드프로페서 5x5", "📊 볼륨 분석"])
past_logs_df = get_past_logs()

# ==========================================
# [탭 4] 📊 볼륨 분석 대시보드 
# ==========================================
with tab_analysis:
    st.header("📊 내 볼륨 분석 대시보드")
    if not current_user:
        st.warning("상단에 사용자 닉네임을 입력하셔야 데이터를 분석할 수 있습니다.")
    elif past_logs_df.empty or '사용자' not in past_logs_df.columns:
        st.info("아직 저장된 구글 시트 기록이 없습니다.")
    else:
        user_df = past_logs_df[(past_logs_df['사용자'] == current_user) & (past_logs_df['완료여부'] == 'O')].copy()
        if user_df.empty:
            st.info("완료된 운동 기록이 아직 없습니다. 오늘의 운동을 저장해 보세요!")
        else:
            ex_to_cat = {}
            for cat, ex_list in st.session_state.exercises.items():
                for ex in ex_list:
                    ex_to_cat[ex] = cat
            
            user_df['부위'] = user_df['종목'].map(ex_to_cat).fillna('기타')
            user_df['볼륨'] = user_df['무게'] * user_df['횟수']
            user_df['날짜_dt'] = pd.to_datetime(user_df['날짜'])
            
            ac1, ac2 = st.columns(2)
            time_filter = ac1.selectbox("기간 단위", ["일간", "주간", "월간"])
            part_filter = ac2.selectbox("부위 선택", ["전체"] + list(st.session_state.exercises.keys()))
            
            if part_filter != "전체":
                user_df = user_df[user_df['부위'] == part_filter]
                
            if time_filter == "일간":
                grouped = user_df.groupby('날짜')['볼륨'].sum().reset_index()
                x_col = '날짜'
            elif time_filter == "주간":
                user_df['주차'] = user_df['날짜_dt'].dt.isocalendar().year.astype(str) + "년 " + user_df['날짜_dt'].dt.isocalendar().week.astype(str) + "주차"
                grouped = user_df.groupby('주차')['볼륨'].sum().reset_index()
                x_col = '주차'
            else: 
                user_df['월'] = user_df['날짜_dt'].dt.strftime('%Y년 %m월')
                grouped = user_df.groupby('월')['볼륨'].sum().reset_index()
                x_col = '월'
                
            st.write("") 
            if grouped.empty:
                st.warning("선택하신 조건에 해당하는 데이터가 없습니다.")
            else:
                st.subheader(f"📈 {part_filter} 부위 {time_filter} 볼륨 변화 (kg)")
                st.bar_chart(data=grouped.set_index(x_col), use_container_width=True)

# ==========================================
# [탭 3] 매드프로페서 5x5
# ==========================================
with tab_mad:
    st.header("🔥 매드프로페서 5x5 (월/수/금) 자동 생성기")
    
    # ⭐ 주차 선택 기능 추가
    col_plate, col_week = st.columns(2)
    min_plate = col_plate.selectbox("가장 가벼운 원판 (kg)", [1.25, 2.5, 5.0], index=0)
    target_week = col_week.number_input("생성할 주차 (Week)", min_value=1, max_value=12, value=1, step=1)
    
    st.write("")
    c1, c2, c3 = st.columns(3)
    with c1:
        sq_w = st.number_input("스쿼트 무게 (1RM/5RM)", value=100.0, step=2.5, key="sq_w")
        sq_r = st.number_input("스쿼트 횟수", value=5, step=1, key="sq_r")
    with c2:
        bp_w = st.number_input("벤치 무게 (1RM/5RM)", value=70.0, step=2.5, key="bp_w")
        bp_r = st.number_input("벤치 횟수", value=5, step=1, key="bp_r")
    with c3:
        dl_w = st.number_input("데드 무게 (1RM/5RM)", value=120.0, step=2.5, key="dl_w")
        dl_r = st.number_input("데드 횟수", value=5, step=1, key="dl_r")
        
    if st.button(f"🚀 {target_week}주차 월/수/금 루틴 3개 일괄 생성", type="primary", use_container_width=True):
        
        # 1. 1주차 기준 기본 시작 무게 계산
        sq_start = calculate_madprofessor_start_weight(sq_w, sq_r, min_plate)
        bp_start = calculate_madprofessor_start_weight(bp_w, bp_r, min_plate)
        dl_start = calculate_madprofessor_start_weight(dl_w, dl_r, min_plate)
        
        # 2. 선택한 주차에 맞춰 점진적 과부하(+2.5kg씩) 자동 추가
        increment = 2.5 * (target_week - 1)
        cur_sq = sq_start + increment
        cur_bp = bp_start + increment
        cur_dl = dl_start + increment
        
        # 바벨로우와 밀리터리 프레스는 벤치프레스 중량을 기준으로 자동 추정
        cur_row = round_to_plate(cur_bp * 0.9, min_plate) 
        cur_ohp = round_to_plate(cur_bp * 0.7, min_plate) 
        
        # 🟢 [월요일] 볼륨 훈련 (5x5 탑세트)
        mon_routine = [
            {"name": "바벨 스쿼트", "target_sets": 5, "target_reps": 5, "suggested_weight": cur_sq},
            {"name": "플랫 벤치프레스", "target_sets": 5, "target_reps": 5, "suggested_weight": cur_bp},
            {"name": "바벨 로우", "target_sets": 5, "target_reps": 5, "suggested_weight": cur_row}
        ]
        
        # 🟡 [수요일] 회복 훈련 (스쿼트는 월요일의 80%, 4세트)
        wed_routine = [
            {"name": "바벨 스쿼트", "target_sets": 4, "target_reps": 5, "suggested_weight": round_to_plate(cur_sq * 0.8, min_plate)},
            {"name": "밀리터리 프레스", "target_sets": 4, "target_reps": 5, "suggested_weight": cur_ohp},
            {"name": "데드리프트", "target_sets": 4, "target_reps": 5, "suggested_weight": cur_dl}
        ]
        
        # 🔴 [금요일] 강도 훈련 (다음 주차 무게를 3회로 먼저 뚫어보기)
        fri_routine = [
            {"name": "바벨 스쿼트", "target_sets": 5, "target_reps": 3, "suggested_weight": cur_sq + 2.5},
            {"name": "플랫 벤치프레스", "target_sets": 5, "target_reps": 3, "suggested_weight": cur_bp + 2.5},
            {"name": "바벨 로우", "target_sets": 5, "target_reps": 3, "suggested_weight": cur_row + 2.5}
        ]
        
        user_tag = current_user if current_user else '기본'
        
        # 구글 시트에 월/수/금 루틴 3개를 동시에 밀어넣습니다.
        with st.spinner("월/수/금 루틴을 생성하고 있습니다..."):
            save_routine_to_sheet(f"[매드프로페서] {target_week}주차 월요일 ({user_tag})", mon_routine)
            save_routine_to_sheet(f"[매드프로페서] {target_week}주차 수요일 ({user_tag})", wed_routine)
            save_routine_to_sheet(f"[매드프로페서] {target_week}주차 금요일 ({user_tag})", fri_routine)
        
        st.success(f"🎉 {target_week}주차 월, 수, 금 루틴 3개가 완벽하게 생성되었습니다! [오늘의 운동] 탭을 확인하세요.")
        st.balloons()
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
                    st.error("구글 시트 삭제 중 오류 발생")
                st.rerun()
        else:
            st.caption("해당 부위에 등록된 종목이 없습니다.")

    st.write("")
    st.subheader("📋 부위별 등록된 종목 목록")
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
        # ⭐ [핵심 기능] 나에게 보이는 루틴만 걸러내기
        # 일반 루틴은 다 보여주고, 매드프로페서는 내 이름이 들어간 것만 보여줍니다.
        visible_manage_routines = [
            r for r in st.session_state.routines.keys() 
            if "[매드프로페서]" not in r or (current_user and f"({current_user})" in r)
        ]
        
        if not visible_manage_routines:
            st.info("현재 편집할 수 있는 루틴이 없습니다.")
        else:
            edit_routine_name = st.selectbox("편집할 루틴을 선택하세요", visible_manage_routines)
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
            if 'last_completed_time' not in st.session_state:
                st.session_state.last_completed_time = 0
    
            # ⭐ [핵심 기능] 나에게 보이는 루틴만 걸러내기 (운동 시작 화면)
            visible_workout_routines = [
                r for r in st.session_state.routines.keys() 
                if "[매드프로페서]" not in r or (current_user and f"({current_user})" in r)
            ]
    
            if not visible_workout_routines:
                st.warning("현재 선택할 수 있는 루틴이 없습니다.")
            else:
                col_sel, col_rest = st.columns([2, 1])
                # 기존의 전체 목록 대신 필터링된 visible_workout_routines를 드롭다운에 넣습니다.
                selected_routine_name = col_sel.selectbox("루틴 목록", visible_workout_routines, label_visibility="collapsed")
                
                if 'rest_sec_pref' not in st.session_state:
                    st.session_state.rest_sec_pref = 60
                rest_sec = col_rest.number_input("⏱️ 휴식 (10초 단위)", min_value=0, value=st.session_state.rest_sec_pref, step=10)
                st.session_state.rest_sec_pref = rest_sec
    
                timer_container = st.empty()
                
                if 'active_routine_name' not in st.session_state or st.session_state.active_routine_name != selected_routine_name:
                    st.session_state.active_routine_name = selected_routine_name
                    st.session_state.active_workout = copy.deepcopy(st.session_state.routines[selected_routine_name])
                    for key in list(st.session_state.keys()):
                        if key.startswith("done_") or key.startswith("prev_done_"):
                            del st.session_state[key]
                    st.session_state.last_completed_time = 0

        db_vol_today = 0
        db_vol_week = 0
        db_vol_month = 0
        current_unsaved_vol = 0
        
        today_str = datetime.now().strftime("%Y-%m-%d")
        this_year_month = datetime.now().strftime("%Y-%m")
        current_year_week = datetime.now().isocalendar()
        this_yw = f"{current_year_week[0]}-{current_year_week[1]}"
        
        if not past_logs_df.empty and '사용자' in past_logs_df.columns:
            user_logs = past_logs_df[(past_logs_df['사용자'] == current_user) & (past_logs_df['완료여부'] == 'O')].copy()
            if not user_logs.empty:
                user_logs['날짜_dt'] = pd.to_datetime(user_logs['날짜'])
                user_logs['볼륨'] = user_logs['무게'] * user_logs['횟수']
                
                db_vol_today = user_logs[user_logs['날짜'] == today_str]['볼륨'].sum()
                db_vol_month = user_logs[user_logs['날짜_dt'].dt.strftime('%Y-%m') == this_year_month]['볼륨'].sum()
                user_logs['year_week'] = user_logs['날짜_dt'].dt.isocalendar().year.astype(str) + "-" + user_logs['날짜_dt'].dt.isocalendar().week.astype(str)
                db_vol_week = user_logs[user_logs['year_week'] == this_yw]['볼륨'].sum()

        vol_dashboard = st.container()
        st.write("---")

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
                        st.session_state.last_completed_time = time.time() # 일괄완료 시에도 타이머 시작
                        st.rerun()

                    st.write("") 

                    default_w = workout.get('suggested_weight', 20.0)
                    default_r = workout['target_reps']
                    sets = workout['target_sets']
                    ex_name = workout['name']
                    
                    is_madprofessor = "[매드프로페서]" in selected_routine_name
                    
                    if is_madprofessor:
                        st.info(f"🔥 매드프로페서 목표 중량: **{default_w}kg**이 우선 적용되었습니다.")
                        master_weight = default_w
                    else:
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
                        
                        # ⭐ 체크박스 상태 추적을 통한 타이머 발동 로직
                        key = f"done_{w_idx}_{i}"
                        prev_key = f"prev_{key}"
                        if prev_key not in st.session_state:
                            st.session_state[prev_key] = False
                            
                        done_val = c4.checkbox("완료", key=key, label_visibility="collapsed")
                        
                        # 만약 방금 '완료'가 체크되었다면? (False -> True)
                        if done_val and not st.session_state[prev_key]:
                            st.session_state.last_completed_time = time.time() # 시계 초기화
                            
                        st.session_state[prev_key] = done_val
                        
                        if done_val:
                            current_unsaved_vol += (weight_val * reps_val)

                        today_logs.append([
                            today_str, current_user, selected_routine_name, ex_name, i, weight_val, reps_val, "O" if done_val else "X"
                        ])

            # ==========================================
            # ⭐ 백그라운드 타이머 & 실시간 볼륨 렌더링
            # ==========================================
            with vol_dashboard:
                st.markdown("### 📈 실시간 볼륨 달성도")
                vc1, vc2, vc3 = st.columns(3)
                vc1.metric("오늘", f"{db_vol_today + current_unsaved_vol:,.0f} kg")
                vc2.metric("이번 주", f"{db_vol_week + current_unsaved_vol:,.0f} kg")
                vc3.metric("이번 달", f"{db_vol_month + current_unsaved_vol:,.0f} kg")
            
            # 타이머 화면 최상단 띄우기
            if st.session_state.last_completed_time > 0 and st.session_state.rest_sec_pref > 0:
                elapsed = time.time() - st.session_state.last_completed_time
                if elapsed < st.session_state.rest_sec_pref:
                    remaining = int(st.session_state.rest_sec_pref - elapsed)
                    
                    html_code = f"""
                    <div style="background-color: rgba(76, 175, 80, 0.1); padding: 12px; border-radius: 8px; text-align: center; border: 2px solid #4CAF50; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                        <h3 style="margin:0; color: #4CAF50; font-family: sans-serif;" id="clock">
                            ⏱️ 휴식 중... 남은 시간: <span style="font-size:1.3em;">{remaining}</span>초
                        </h3>
                    </div>
                    <script>
                        let time = {remaining};
                        let el = document.getElementById('clock');
                        let timer = setInterval(function() {{
                            time--;
                            if(time > 0) {{
                                el.innerHTML = '⏱️ 휴식 중... 남은 시간: <span style="font-size:1.3em;">' + time + '</span>초';
                            }} else {{
                                el.innerHTML = '🔔 <span style="color:#d32f2f;">휴식 종료! 다음 세트를 시작하세요!</span> 💪';
                                clearInterval(timer);
                            }}
                        }}, 1000);
                    </script>
                    """
                    with timer_container:
                        components.html(html_code, height=75)

            st.divider()
            if st.button("🚀 오늘 운동 결과 최종 저장하기", type="primary", use_container_width=True):
                with st.spinner('구글 시트에 기록을 저장하는 중입니다...'):
                    try:
                        logs_sheet = doc.worksheet("Logs")
                        logs_sheet.append_rows(today_logs)
                        st.success("🎉 구글 시트(Logs)에 데이터가 완벽하게 저장되었습니다!")
                        get_past_logs.clear() 
                        st.balloons()
                    except Exception as e:
                        st.error(f"저장 중 오류가 발생했습니다. (에러: {e})")
