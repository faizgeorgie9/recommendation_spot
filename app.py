import streamlit as st
import pandas as pd
import datetime
import io
import urllib.parse
from sqlalchemy import create_engine

# ==========================================
# 1. KONFIGURASI GLOBAL
# ==========================================
TOTAL_DETIK_HARI = 64800  # 18 Jam Operasional
BASE_SPOT = 135
TARGET_L_MIN = BASE_SPOT * 1.10  # 148.5 (110%)
TARGET_L_MAX = BASE_SPOT * 1.15  # 155.25 (115%)

# ==========================================
# 2. FUNGSI PERHITUNGAN UTAMA & SEQUENCE
# ==========================================
def calculate_metrics_daily(df_daily):
    df = df_daily.copy()
    
    # FIX: Pastikan kolom 'loop' selalu ada meskipun data kosong
    if 'loop' not in df.columns:
        df['loop'] = pd.Series(dtype='float64')
    
    if len(df) == 0:
        return df, pd.DataFrame([{
            'total_duration_sec': 0, 'total_spot': 0, 'total_cycle_duration': 0,
            'jumlah_loop_perhari': 0, 'target_l_min': TARGET_L_MIN, 'target_l_max': TARGET_L_MAX, 'status_l_tercapai': False
        }])
        
    total_duration_sum = df['duration'].sum()
    total_spot_sum = df['total_spot'].sum()
    
    df['loop'] = df['total_spot'] / BASE_SPOT
    total_cycle_duration = (df['duration'] * df['loop']).sum()
    jumlah_loop_perhari = TOTAL_DETIK_HARI / total_cycle_duration if total_cycle_duration > 0 else 0
    
    summary_data = {
        'total_duration_sec': total_duration_sum,
        'total_spot': total_spot_sum,
        'total_cycle_duration': total_cycle_duration,
        'jumlah_loop_perhari': jumlah_loop_perhari,
        'target_l_min': TARGET_L_MIN,
        'target_l_max': TARGET_L_MAX,
        'status_l_tercapai': TARGET_L_MIN <= jumlah_loop_perhari <= TARGET_L_MAX
    }
    
    return df, pd.DataFrame([summary_data])

def generate_playlist_sequence(df):
    sequence_data = []
    if len(df) == 0:
        return pd.DataFrame(columns=['Urutan', 'Date', 'Screen', 'File Name', 'Duration', 'Spot'])
        
    max_loop = int(df['loop'].round().max())
    urutan = 1
    
    for putaran in range(1, max_loop + 1):
        for index, row in df.iterrows():
            if round(row['loop']) >= putaran:
                sequence_data.append({
                    'Urutan': urutan,
                    'Date': row['date'],
                    'Screen': row['screen_name'],
                    'File Name': row['file_name'],
                    'Duration': row['duration'],
                    'Spot': row['total_spot']
                })
                urutan += 1
    return pd.DataFrame(sequence_data)

def hitung_rekomendasi(df_current):
    if len(df_current) == 0:
        C_current = 0
    else:
        C_current = (df_current['duration'] * (df_current['total_spot'] / BASE_SPOT)).sum()
        
    C_target_mid = TOTAL_DETIK_HARI / ((TARGET_L_MIN + TARGET_L_MAX) / 2)
    
    durations = [30.0, 15.0, 7.5]
    spots = [540, 270, 135]
    rekomendasi_data = []
    
    for d in durations:
        for s in spots:
            unit_dur_cycle = d * (s / BASE_SPOT)
            k_ideal = (C_target_mid - C_current) / unit_dur_cycle if unit_dur_cycle > 0 else 0
            k = max(0, round(k_ideal))
            
            if k > 0:
                L_estimasi = TOTAL_DETIK_HARI / (C_current + (k * unit_dur_cycle))
                status = "✅ Pas Target" if TARGET_L_MIN <= L_estimasi <= TARGET_L_MAX else "⚠️ Mendekati"
                rekomendasi_data.append({
                    "Durasi Paket": f"{d}s", "Commited Spot": f"{s}x",
                    "Max Klien Ditambahkan": k, "Estimasi Loop/Hari": f"{L_estimasi:.2f}", "Status": status
                })
            else:
                rekomendasi_data.append({
                    "Durasi Paket": f"{d}s", "Commited Spot": f"{s}x",
                    "Max Klien Ditambahkan": 0, "Estimasi Loop/Hari": "-", "Status": "❌ Penuh"
                })
    return pd.DataFrame(rekomendasi_data)

# ==========================================
# 3. FUNGSI EXPORT KE SQL SERVER
# ==========================================
def export_to_sql_server(df):
    """Mengekspor dataframe ke database SQL Server menggunakan SQLAlchemy"""
    try:
        server = r'PSWWM2604\SQLEXPRESS'
        database = 'commited_spot'
        driver = 'ODBC Driver 17 for SQL Server'
        
        connection_string = f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};Trusted_Connection=yes;"
        connection_url = f"mssql+pyodbc:///?odbc_connect={urllib.parse.quote_plus(connection_string)}"
        engine = create_engine(connection_url)
        
        # Simpan tabel ke dalam SQL dengan nama 'tb_showing_commitment'
        # if_exists='replace' akan menimpa tabel lama jika sudah ada. (Ubah ke 'append' jika ingin menambah baris)
        df.to_sql('tb_showing_commitment', con=engine, if_exists='replace', index=False)
        return True, "Data berhasil di-push ke SQL Server!"
    except Exception as e:
        return False, f"Gagal mengekspor data: {str(e)}"

# ==========================================
# 4. INISIALISASI SESSION STATE
# ==========================================
if 'sistem_siap' not in st.session_state: st.session_state.sistem_siap = False
if 'df_master' not in st.session_state: st.session_state.df_master = pd.DataFrame()
if 'logs' not in st.session_state: st.session_state.logs = []
if 'notif' not in st.session_state: st.session_state.notif = None 

def initialize_system():
    tgl_hari_ini = datetime.date.today()
    data_awal = []
    screens = ["LED Sudirman", "LED Thamrin"]
    
    for i in range(3):
        tgl = tgl_hari_ini + datetime.timedelta(days=i)
        for screen in screens:
            data_awal.extend([
                [screen, "indofood_15s.mp4", tgl, 15, 270, 15*270],
                [screen, "telkomsel_30s.mp4", tgl, 30, 135, 30*135],
                [screen, "gojek_7_5s.mp4", tgl, 7.5, 540, 7.5*540]
            ])
            
    st.session_state.df_master = pd.DataFrame(data_awal, columns=['screen_name', 'file_name', 'date', 'duration', 'total_spot', 'total_duration'])
    st.session_state.sistem_siap = True
    st.session_state.logs.append("✅ Sistem diinisialisasi dengan struktur data baru.")

# ==========================================
# 5. FUNGSI BOOKING RANGE TANGGAL
# ==========================================
def booking_slot(screen, file_name, start_date, end_date, req_duration, req_spot, qty):
    if start_date > end_date:
        st.error("❌ Start Date tidak boleh lebih besar dari End Date.")
        return False

    date_range = pd.date_range(start_date, end_date).date
    
    new_rows = []
    for d in date_range:
        for _ in range(qty):
            new_rows.append({
                "screen_name": screen,
                "file_name": file_name,
                "date": d,
                "duration": float(req_duration),
                "total_spot": int(req_spot),
                "total_duration": float(req_duration) * int(req_spot)
            })
            
    st.session_state.df_master = pd.concat([st.session_state.df_master, pd.DataFrame(new_rows)], ignore_index=True)
    st.session_state.logs.append(f"📥 '{file_name}' ({qty} Paket) dijadwalkan di {screen} dari {start_date} s/d {end_date}.")
    st.session_state.notif = {"msg": f"✅ Penjadwalan berhasil disimpan!", "icon": "🎉"}
    return True

def batal_booking(screen, date_batal, file_name):
    df_m = st.session_state.df_master
    mask = (df_m['screen_name'] == screen) & (df_m['date'] == date_batal) & (df_m['file_name'] == file_name)
    
    if mask.any():
        idx = df_m[mask].index[0]
        st.session_state.df_master = df_m.drop(idx).reset_index(drop=True)
        st.session_state.logs.append(f"🗑️ '{file_name}' dibatalkan untuk layar {screen} pada {date_batal}.")
        return True
    return False

# ==========================================
# 6. TAMPILAN GUI STREAMLIT
# ==========================================
st.set_page_config(page_title="LED Booking & Audit System", layout="wide")
st.title("📺 Sistem Manajemen & Rekonsiliasi LED")

if not st.session_state.sistem_siap:
    st.info("Sistem belum memuat database. Klik tombol di bawah untuk memulai.")
    if st.button("🚀 Load Database LED"):
        initialize_system()
        st.rerun()
else:
    if st.session_state.notif:
        st.toast(st.session_state.notif["msg"], icon=st.session_state.notif["icon"])
        st.session_state.notif = None 

    # --- PENGATURAN MULTI-TAB ---
    tab1, tab2 = st.tabs(["📅 Perencanaan & Jadwal Tayang", "⚖️ Audit (Compare Daily Summary)"])
    
    # =========================================================
    # TAB 1 : BOOKING & MANAJEMEN PLAYLIST
    # =========================================================
    with tab1:
        st.markdown("### Filter Tampilan Saat Ini")
        c_f1, c_f2 = st.columns(2)
        
        layar_list = st.session_state.df_master['screen_name'].unique().tolist()
        if not layar_list: layar_list = ["LED Sudirman", "LED Thamrin"]
        
        selected_screen = c_f1.selectbox("Pilih Layar LED:", layar_list)
        selected_date = c_f2.date_input("Lihat Data Pada Tanggal:", datetime.date.today())
        
        st.markdown("---")
        
        df_view = st.session_state.df_master[(st.session_state.df_master['screen_name'] == selected_screen) & (st.session_state.df_master['date'] == selected_date)]
        
        df_calc, summary_calc = calculate_metrics_daily(df_view)
        L_saat_ini = summary_calc['jumlah_loop_perhari'].iloc[0]
        status_target = summary_calc['status_l_tercapai'].iloc[0]

        # METRIK MONITORING
        col_m1, col_m2, col_m3 = st.columns(3)
        if status_target:
            L_color, status_teks = "normal", "✅ TARGET TERCAPAI"
        elif L_saat_ini > TARGET_L_MAX:
            L_color, status_teks = "normal", "⚠️ Kekurangan Klien (Terlalu Cepat)"
        else:
            L_color, status_teks = "inverse", "🚨 Kelebihan Beban (Terlalu Lambat)"
            if L_saat_ini == 0: status_teks = "⚪ Kosong"
            
        col_m1.metric(f"Putaran (L) - {selected_screen}", f"{L_saat_ini:.2f} Kali", status_teks, delta_color=L_color)
        col_m2.metric("Target Ideal (110% - 115%)", f"{TARGET_L_MIN:.2f} - {TARGET_L_MAX:.2f} Kali")
        col_m3.metric("Total Commited Spot", f"{summary_calc['total_spot'].iloc[0]} Spot")

        # KONTEN UTAMA
        col1, col2 = st.columns([2, 1])
        with col1:
            st.subheader(f"📋 Rekomendasi Penambahan per {selected_date}")
            df_rekomendasi = hitung_rekomendasi(df_calc)
            st.dataframe(df_rekomendasi, use_container_width=True)
                
            st.subheader(f"📊 Daftar Putar (Showing Commitment)")
            df_edit = df_calc[['file_name', 'duration', 'total_spot', 'loop']].copy()
            df_edit.insert(0, "Hapus", False)
            
            edited_df = st.data_editor(
                df_edit,
                column_config={"Hapus": st.column_config.CheckboxColumn("Batal", default=False)},
                disabled=list(df_edit.columns)[1:], 
                hide_index=True, use_container_width=True
            )
            
            if st.button("🗑️ Eksekusi Hapus yang Dicentang", type="primary"):
                batal_list = edited_df[edited_df["Hapus"] == True]["file_name"].tolist()
                for fn in batal_list:
                    batal_booking(selected_screen, selected_date, fn)
                st.rerun() 
                
            st.subheader("📅 Preview Urutan Tayang (Playlog Sequence)")
            df_sequence = generate_playlist_sequence(df_calc)
            st.dataframe(df_sequence.set_index('Urutan'), use_container_width=True)
            
        with col2:
            st.subheader("📝 Tambah Jadwal Tayang Baru")
            with st.form("form_booking"):
                f_screen = st.selectbox("Layar Target", layar_list)
                f_file = st.text_input("File Name (.mp4)", placeholder="iklan_baru.mp4")
                
                c_d1, c_d2 = st.columns(2)
                f_start = c_d1.date_input("Mulai Tanggal", selected_date)
                f_end = c_d2.date_input("Sampai Tanggal", selected_date)
                
                c_s1, c_s2, c_s3 = st.columns(3)
                f_qty = c_s1.number_input("Jml Paket", min_value=1, value=1)
                f_dur = c_s2.selectbox("Durasi (s)", [30.0, 15.0, 7.5])
                f_spot = c_s3.selectbox("Spot/Hari", [540, 270, 135])
                
                if st.form_submit_button("Booking ke Sistem", use_container_width=True):
                    if f_file:
                        if booking_slot(f_screen, f_file, f_start, f_end, f_dur, f_spot, f_qty):
                            st.rerun()
                    else:
                        st.error("Nama file tidak boleh kosong!")

            # -----------------------------------------------------
            # TOMBOL EXPORT KE SQL SERVER
            # -----------------------------------------------------
            st.markdown("---")
            st.subheader("🗄️ Sinkronisasi Database")
            st.caption("Push seluruh data Master Commited Spot ke SQL Server.")
            
            if st.button("🚀 Push ke SQL Server", type="primary", use_container_width=True):
                with st.spinner("Menghubungkan ke SQL Server..."):
                    success, msg = export_to_sql_server(st.session_state.df_master)
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)
            # -----------------------------------------------------

    # =========================================================
    # TAB 2 : REKONSILIASI (COMPARE GAP)
    # =========================================================
    with tab2:
        st.markdown("### ⚖️ Audit: Showing Commitment vs Daily Summary")
        st.info("Simulasi perbandingan data target komitmen harian yang ada di database kita dengan laporan aktual dari mesin LED.")
        
        if st.button("🔄 Simulasikan Tarik Laporan Aktual Mesin (Contoh)"):
            df_aktual = st.session_state.df_master.copy()
            import numpy as np
            np.random.seed(42)
            df_aktual['actual_spot'] = df_aktual['total_spot'] - np.random.randint(0, 15, size=len(df_aktual)) 
            df_aktual['actual_duration'] = df_aktual['actual_spot'] * df_aktual['duration']
            
            df_planned = st.session_state.df_master.copy()
            df_planned = df_planned.rename(columns={'total_spot': 'planned_spot', 'total_duration': 'planned_duration'})
            
            df_audit = pd.merge(df_planned, df_aktual[['screen_name', 'file_name', 'date', 'actual_spot', 'actual_duration']], 
                                on=['screen_name', 'file_name', 'date'], how='left')
            
            df_audit['Diff Spot'] = df_audit['actual_spot'] - df_audit['planned_spot']
            df_audit['Diff Duration'] = df_audit['actual_duration'] - df_audit['planned_duration']
            
            df_audit['Status'] = df_audit['Diff Spot'].apply(lambda x: "✅ Tercapai" if x >= 0 else "⚠️ Kurang Tayang")
            
            st.session_state.df_audit_result = df_audit
            st.success("Laporan Aktual berhasil disimulasikan dan digabungkan!")

        if 'df_audit_result' in st.session_state:
            st.markdown("#### Tabel Selisih (Gap Analysis)")
            st.dataframe(st.session_state.df_audit_result, use_container_width=True)
            
            output_audit = io.BytesIO()
            with pd.ExcelWriter(output_audit, engine='xlsxwriter') as writer_audit:
                st.session_state.df_audit_result.to_excel(writer_audit, sheet_name='Audit_Gap_Report', index=False)
                
            st.download_button("📥 Download Laporan Audit (Excel)", data=output_audit.getvalue(), 
                               file_name="Laporan_Gap_LED.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
