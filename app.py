import streamlit as st
import pandas as pd
import random
import io

# ==========================================
# 1. FUNGSI PERHITUNGAN UTAMA
# ==========================================
def calculate_metrics(df_input):
    df = df_input.copy()
    if 'total_duration_daily' not in df.columns:
        df['total_duration_daily'] = df['duration'] * df['commited_spot']
        
    total_duration_sum = df['duration'].sum()
    total_spot_sum = df['commited_spot'].sum()
    total_filled_operational = df['total_duration_daily'].sum()
    total_duration_operational = 18 * 3600  # 64,800 detik
    
    summary_data = {
        'total_duration_sec': total_duration_sum,
        'total_spot': total_spot_sum,
        'total_filled_operational': total_filled_operational,
        'total_duration_operational': total_duration_operational,
        'remain_quota_sec': total_duration_operational - total_filled_operational,
        'total_loop_capacity': total_duration_operational / total_duration_sum if total_duration_sum > 0 else 0
    }
    summary_df = pd.DataFrame([summary_data])
    summary_df['percent_remain_quota'] = (summary_df['remain_quota_sec'] / summary_df['total_duration_operational']) * 100
    
    df['n1'] = df['commited_spot'] / summary_df['total_loop_capacity'].iloc[0]
    df['n2'] = df['n1'] / df['n1'].iloc[0]
    df['loop'] = df['n2'] * 4
    df['loop'] = df['loop'].round().astype(int) 
    df['total_loop_duration'] = df['duration'] * df['loop']
    
    return df, summary_df

# ==========================================
# 2. INISIALISASI SESSION STATE
# ==========================================
if 'sistem_siap' not in st.session_state:
    st.session_state.sistem_siap = False

if 'sheets_data' not in st.session_state:
    st.session_state.sheets_data = {}

if 'df_simulasi' not in st.session_state:
    st.session_state.df_simulasi = None

if 'sheet_counter' not in st.session_state:
    st.session_state.sheet_counter = 3
    
if 'logs' not in st.session_state:
    st.session_state.logs = []


def initialize_system():
    data_awal = [
        ["client a", 7.5, 540], ["client b", 15, 270],
        ["client c", 7.5, 270], ["client d", 30, 135],
        ["client e", 7.5, 135], ["client f", 15, 135],
        ["client g", 7.5, 270], ["client test", 30, 540]
    ]
    df_awal = pd.DataFrame(data_awal, columns=["client", "duration", "commited_spot"])
    
    df_awal_calc, summary_awal = calculate_metrics(df_awal)
    st.session_state.sheets_data["1_Kondisi_Awal"] = (df_awal_calc, summary_awal)
    
    total_duration_operational = 18 * 3600
    threshold_sec = 0.10 * total_duration_operational
    sellable_quota = summary_awal['remain_quota_sec'].iloc[0] - threshold_sec
    
    durations = [30, 15, 7.5]
    spots_list = [540, 405, 270, 135]
    packages = [{'duration': d, 'commited_spot': s, 'daily_dur': d*s} for d in durations for s in spots_list]
    
    random.seed(42) 
    random.shuffle(packages)
    
    recom_list = []
    current_fill = 0
    idx = 1
    
    while True:
        added = False
        random.shuffle(packages)
        for pkg in packages:
            if current_fill + pkg['daily_dur'] <= sellable_quota:
                recom_list.append({
                    "client": f"[SLOT KOSONG] Rekomendasi {idx}",
                    "duration": pkg['duration'],
                    "commited_spot": pkg['commited_spot'],
                    "original_slot_name": f"[SLOT KOSONG] Rekomendasi {idx}" 
                })
                current_fill += pkg['daily_dur']
                idx += 1
                added = True
        if not added or current_fill > sellable_quota - 1000:
            break
            
    df_rekomendasi = pd.DataFrame(recom_list)
    df_awal_copy = df_awal.copy()
    df_awal_copy['original_slot_name'] = df_awal_copy['client']
    
    st.session_state.df_simulasi = pd.concat([df_awal_copy, df_rekomendasi], ignore_index=True)
    df_full_calc, summary_full = calculate_metrics(st.session_state.df_simulasi)
    st.session_state.sheets_data["2_Full_Rekomendasi"] = (df_full_calc, summary_full)
    
    st.session_state.sistem_siap = True
    st.session_state.logs.append("Sistem berhasil diinisialisasi. Slot kosong siap dijual.")

# ==========================================
# 3. FUNGSI BOOKING & BATAL
# ==========================================
def booking_slot(nama_klien, req_duration, req_spot):
    df_sim = st.session_state.df_simulasi
    mask = (df_sim['client'].str.contains(r"\[SLOT KOSONG\]")) & (df_sim['duration'] == float(req_duration)) & (df_sim['commited_spot'] == int(req_spot))
    df_target = df_sim[mask]
    
    if df_target.empty:
        st.error(f"❌ Slot dengan Durasi {req_duration}s dan Spot {req_spot} tidak tersedia!")
        return
        
    idx = df_target.index[0]
    st.session_state.df_simulasi.at[idx, 'client'] = nama_klien
    
    df_calc, summary_calc = calculate_metrics(st.session_state.df_simulasi)
    sheet_name = f"{st.session_state.sheet_counter}_Booking_{nama_klien[:10]}"
    st.session_state.sheets_data[sheet_name] = (df_calc, summary_calc)
    st.session_state.sheet_counter += 1
    
    st.session_state.logs.append(f"✅ BINGO! Klien '{nama_klien}' booked (Dur: {req_duration}s, Spot: {req_spot})")
    st.success(f"Berhasil booking untuk {nama_klien}!")

def batal_booking(nama_klien):
    df_sim = st.session_state.df_simulasi
    mask = df_sim['client'] == nama_klien
    df_target = df_sim[mask]
    
    if df_target.empty:
        st.error(f"❌ Klien '{nama_klien}' tidak ditemukan!")
        return
        
    idx = df_target.index[0]
    nama_original = df_sim.at[idx, 'original_slot_name']
    
    st.session_state.df_simulasi.at[idx, 'client'] = nama_original
    
    df_calc, summary_calc = calculate_metrics(st.session_state.df_simulasi)
    sheet_name = f"{st.session_state.sheet_counter}_Cancel_{nama_klien[:10]}"
    st.session_state.sheets_data[sheet_name] = (df_calc, summary_calc)
    st.session_state.sheet_counter += 1
    
    st.session_state.logs.append(f"⚠️ PEMBATALAN: Klien '{nama_klien}' dihapus. Slot kembali kosong.")
    st.warning(f"Booking {nama_klien} berhasil dibatalkan!")

# ==========================================
# 4. TAMPILAN GUI STREAMLIT
# ==========================================
st.set_page_config(page_title="LED Booking System", layout="wide")
st.title("📺 Sistem Booking Slot Iklan LED")
st.markdown("Simulasi *booking* dan manajemen slot kosong untuk *digital billboard*.")

if not st.session_state.sistem_siap:
    st.info("Sistem belum berjalan. Klik tombol di bawah untuk membuat slot rekomendasi.")
    if st.button("🚀 Inisialisasi Sistem"):
        initialize_system()
        st.rerun()
else:
    # --- HITUNG METRIK VISUAL ---
    df_sim = st.session_state.df_simulasi
    
    # Hitung total detik yang di-booking oleh klien asli (bukan slot kosong)
    mask_terjual = ~df_sim['client'].str.contains(r"\[SLOT KOSONG\]")
    total_detik_terjual = (df_sim[mask_terjual]['duration'] * df_sim[mask_terjual]['commited_spot']).sum()
    
    total_operasional = 18 * 3600
    threshold = 0.10 * total_operasional
    kapasitas_maksimal_jual = total_operasional - threshold
    
    persen_terjual = (total_detik_terjual / kapasitas_maksimal_jual) * 100
    persen_sisa = 100 - persen_terjual
    
    # Hitung jumlah slot
    total_slot_rekomendasi = len(df_sim[df_sim['original_slot_name'].str.contains(r"\[SLOT KOSONG\]", na=False)])
    slot_terisi = len(df_sim[(~df_sim['client'].str.contains(r"\[SLOT KOSONG\]")) & (df_sim['original_slot_name'].str.contains(r"\[SLOT KOSONG\]", na=False))])
    sisa_slot = total_slot_rekomendasi - slot_terisi

    # --- TAMPILKAN METRIK DI ATAS ---
    st.markdown("---")
    st.subheader("📈 Status Kapasitas LED Saat Ini")
    
    # Menampilkan progress bar yang intuitif
    st.progress(persen_terjual / 100)
    
    # Menampilkan angka metrik berjajar
    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("Kuota Slot Terjual", f"{persen_terjual:.1f}%", f"{slot_terisi} slot")
    col_m2.metric("Sisa Kuota Tersedia", f"{persen_sisa:.1f}%", f"{sisa_slot} slot tersisa", delta_color="inverse")
    col_m3.metric("Waktu Tersedia", f"{int((kapasitas_maksimal_jual - total_detik_terjual) / 60)} Menit", "Siap dijual")
    st.markdown("---")

    # --- TAMPILAN UTAMA ---
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📋 Daftar Slot Kosong (Tersedia)")
        mask_kosong = df_sim['client'].str.contains(r"\[SLOT KOSONG\]")
        df_kosong = df_sim[mask_kosong]
        
        if df_kosong.empty:
            st.warning("Semua slot sudah terjual!")
        else:
            summary_kosong = df_kosong.groupby(['duration', 'commited_spot']).size().reset_index(name='jumlah_slot')
            st.dataframe(summary_kosong, use_container_width=True)
            
        st.subheader("📊 Tabel Playlist Saat Ini")
        df_tampil = df_sim.drop(columns=['original_slot_name'], errors='ignore')
        st.dataframe(df_tampil, use_container_width=True)
        
    with col2:
        st.subheader("📝 Form Booking Klien")
        with st.form("form_booking"):
            nama_baru = st.text_input("Nama Klien Baru")
            dur_baru = st.selectbox("Pilih Durasi (Detik)", [30.0, 15.0, 7.5])
            spot_baru = st.selectbox("Pilih Commited Spot", [540, 405, 270, 135])
            btn_book = st.form_submit_button("Booking Slot!")
            if btn_book and nama_baru:
                booking_slot(nama_baru, dur_baru, spot_baru)
                st.rerun() # Refresh agar progress bar langsung update
                
        st.subheader("🗑️ Form Batal Booking")
        with st.form("form_batal"):
            nama_batal = st.text_input("Nama Klien yang Batal")
            btn_batal = st.form_submit_button("Batalkan Slot")
            if btn_batal and nama_batal:
                batal_booking(nama_batal)
                st.rerun() # Refresh agar progress bar langsung update
                
        st.subheader("📜 Log Aktivitas")
        for log in reversed(st.session_state.logs[-5:]): # Tampilkan 5 log terakhir saja
            st.text(log)
            
        st.subheader("💾 Export ke Excel")
        output = io.BytesIO()
        writer = pd.ExcelWriter(output, engine='xlsxwriter')
        for sheet_name, (df_main, df_summary) in st.session_state.sheets_data.items():
            df_to_save = df_main.drop(columns=['original_slot_name'], errors='ignore')
            df_to_save.to_excel(writer, sheet_name=sheet_name, index=False, startrow=0)
            
            start_row_summary = len(df_to_save) + 2
            worksheet = writer.sheets[sheet_name]
            worksheet.write_string(start_row_summary, 0, '--- SUMMARY METRICS ---')
            df_summary.to_excel(writer, sheet_name=sheet_name, index=False, startrow=start_row_summary + 1)
        writer.close()
        
        st.download_button(
            label="Download Laporan Excel",
            data=output.getvalue(),
            file_name="Simulasi_Booking_Slot_Iklan.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
