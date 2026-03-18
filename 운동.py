# ==========================================
# [탭 3] 매드프로페서 5x5
# ==========================================
with tab_mad:
    st.header("🔥 매드프로페서 (월/수/금) 엑셀 연동 커스텀 생성기")
    
    col_plate, col_week = st.columns(2)
    min_plate = col_plate.selectbox("가장 가벼운 원판 (kg)", [1.25, 2.5, 5.0], index=0)
    target_week = col_week.number_input("생성할 주차 (Week)", min_value=1, max_value=12, value=1, step=1)
    
    st.write("### 🏋️ 메인 종목 1RM (또는 5RM) 입력")
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

    st.write("---")
    st.write("### 🛠️ 요일별 보조운동(Accessory) 선택")
    st.caption("엑셀 시트와 동일하게 부위별 리스트가 반영되어 있습니다. (생성 시 기본 3~4세트로 자동 세팅됩니다.)")
    
    # ⭐ 엑셀 이미지에 있는 보조운동 리스트 완벽 이식
    acc_dict = {
        "이두": ["바벨 이두컬", "이지바 이두컬", "덤벨 이두컬", "해머컬", "프리처컬"],
        "삼두": ["트라이셉스 푸시다운", "클로즈그립 푸시업", "스컬크러셔", "덤벨 플로어프레스", "덤벨 풀오버", "딥스", "트라이셉스 킥백"],
        "등": ["랫풀다운", "바벨로우", "펜들레이로우", "풀업", "친업", "덤벨로우", "인버티드로우", "시티드로우", "실로우"],
        "어깨": ["프론트 레이즈", "사이드 레터럴 레이즈", "숄더 프레스", "업라이트 로우", "오버헤드 프레스"],
        "대퇴사두": ["스플릿 스쿼트", "고블릿 스쿼트", "핵스쿼트", "런지", "레그익스텐션", "레그프레스", "스텝업"],
        "코어/복근": ["AB슬라이드", "데드버그", "플랭크", "행잉레그레이즈", "크런치"],
        "후면사슬": ["백레이즈", "굿모닝", "힙스러스트", "루마니안데드리프트", "글루트햄레이즈", "레그컬", "리버스하이퍼"]
    }
    
    # 월요일 보조 (2개)
    st.markdown("**🟦 [월요일] 보조 2개 선택 (등, 코어/복근)**")
    mc1, mc2 = st.columns(2)
    mon_back = mc1.selectbox("등 (월요일)", acc_dict["등"], index=acc_dict["등"].index("펜들레이로우"))
    mon_core = mc2.selectbox("코어/복근", acc_dict["코어/복근"], index=acc_dict["코어/복근"].index("플랭크"))

    # 수요일 보조 (4개)
    st.markdown("**🟨 [수요일] 보조 4개 선택 (어깨, 대퇴사두, 이두, 삼두)**")
    wc1, wc2, wc3, wc4 = st.columns(4)
    wed_sh = wc1.selectbox("어깨", acc_dict["어깨"], index=acc_dict["어깨"].index("숄더 프레스"))
    wed_quad = wc2.selectbox("대퇴사두", acc_dict["대퇴사두"], index=acc_dict["대퇴사두"].index("핵스쿼트"))
    wed_bi = wc3.selectbox("이두", acc_dict["이두"], index=acc_dict["이두"].index("바벨 이두컬"))
    wed_tri = wc4.selectbox("삼두", acc_dict["삼두"], index=acc_dict["삼두"].index("클로즈그립 푸시업"))

    # 금요일 보조 (2개)
    st.markdown("**🟦 [금요일] 보조 2개 선택 (등, 후면사슬)**")
    fc1, fc2 = st.columns(2)
    fri_back = fc1.selectbox("등 (금요일)", acc_dict["등"], index=acc_dict["등"].index("풀업"))
    fri_post = fc2.selectbox("후면사슬", acc_dict["후면사슬"], index=acc_dict["후면사슬"].index("루마니안데드리프트"))

    if st.button(f"🚀 {target_week}주차 월/수/금 맞춤형 루틴 생성", type="primary", use_container_width=True):
        
        sq_start = calculate_madprofessor_start_weight(sq_w, sq_r, min_plate)
        bp_start = calculate_madprofessor_start_weight(bp_w, bp_r, min_plate)
        dl_start = calculate_madprofessor_start_weight(dl_w, dl_r, min_plate)
        
        increment = 2.5 * (target_week - 1)
        cur_sq = sq_start + increment
        cur_bp = bp_start + increment
        cur_dl = dl_start + increment
        
        # 🟢 [월요일 루틴]: 스쿼트, 벤치 + 보조 2개
        mon_routine = [
            {"name": "바벨 스쿼트", "target_sets": 5, "target_reps": 5, "suggested_weight": cur_sq},
            {"name": "플랫 벤치프레스", "target_sets": 5, "target_reps": 5, "suggested_weight": cur_bp},
            {"name": mon_back, "target_sets": 4, "target_reps": 10, "suggested_weight": 40.0},
            {"name": mon_core, "target_sets": 3, "target_reps": 10, "suggested_weight": 0.0} 
        ]
        
        # 🟡 [수요일 루틴]: 데드리프트 메인 + 보조 4개 (엑셀 양식 완벽 반영)
        wed_routine = [
            {"name": "데드리프트", "target_sets": 4, "target_reps": 5, "suggested_weight": cur_dl},
            {"name": wed_sh, "target_sets": 4, "target_reps": 10, "suggested_weight": 20.0},
            {"name": wed_quad, "target_sets": 4, "target_reps": 10, "suggested_weight": 40.0},
            {"name": wed_bi, "target_sets": 3, "target_reps": 12, "suggested_weight": 20.0},
            {"name": wed_tri, "target_sets": 3, "target_reps": 12, "suggested_weight": 20.0}
        ]
        
        # 🔴 [금요일 루틴]: 스쿼트, 벤치 + 보조 2개 + 데드 테크닉 (엑셀 양식 반영)
        fri_routine = [
            {"name": "바벨 스쿼트", "target_sets": 5, "target_reps": 3, "suggested_weight": cur_sq + 2.5},
            {"name": "플랫 벤치프레스", "target_sets": 5, "target_reps": 3, "suggested_weight": cur_bp + 2.5},
            {"name": fri_back, "target_sets": 4, "target_reps": 10, "suggested_weight": 0.0}, # 풀업 등 맨몸 대비
            {"name": fri_post, "target_sets": 4, "target_reps": 10, "suggested_weight": 50.0},
            {"name": "데드리프트 (테크닉)", "target_sets": 5, "target_reps": 5, "suggested_weight": round_to_plate(cur_dl * 0.6, min_plate)}
        ]
        
        user_tag = current_user if current_user else '기본'
        
        with st.spinner("엑셀 맞춤형 보조운동이 포함된 루틴을 굽고 있습니다..."):
            save_routine_to_sheet(f"[매드프로페서] {target_week}주차 월요일 ({user_tag})", mon_routine)
            save_routine_to_sheet(f"[매드프로페서] {target_week}주차 수요일 ({user_tag})", wed_routine)
            save_routine_to_sheet(f"[매드프로페서] {target_week}주차 금요일 ({user_tag})", fri_routine)
        
        st.success(f"🎉 {target_week}주차 요일별 커스텀 보조운동 루틴 생성 완료! [오늘의 운동] 탭을 확인하세요.")
        st.balloons()
