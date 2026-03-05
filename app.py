import streamlit as st
import pandas as pd
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
    
    if total_duration_sum > 0:
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
    st.session_state.sheet_counter = 2
if 'logs' not in st.session_state:
    st.session_state.logs = []
if 'notif' not in st.session_state:
    st.session_state.notif = None # Untuk menyimpan pop-up toast

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
    st.session_state.df_simulasi = df_awal.copy()
    
    st.session_state.sistem_siap = True
    st.session_state.logs.append("✅ Sistem diinisialisasi. Playlist awal dimuat.")
    st.session_state.notif = {"msg": "Sistem berhasil dimuat!", "icon": "🚀"}

# ==========================================
# 3. FUNGSI BOOKING & BATAL
# ==========================================
def booking_slot(nama_klien, req_duration, req_spot, sellable_quota):
    daily_dur_req = req_duration * req_spot
    
    # LOGIKA PENOLAKAN JIKA MELEWATI BATAS 10%
    if daily_dur_req > sellable_quota:
        st.toast("🚨 GAGAL: Kuota penuh atau tidak mencukupi!", icon="❌")
        st.error(f"❌ **Gagal menambahkan '{nama_klien}'!**\n\nPaket ini membutuhkan **{daily_dur_req} detik**, sedangkan sisa kuota jual Anda hanya **{int(sellable_quota)} detik**. Anda telah menyentuh batas aman (Threshold 10%).")
        return False # Return False agar layar tidak ter-refresh dan error bisa dibaca user
        
    # Tambahkan klien ke dataframe
    new_row = pd.DataFrame([{
        "client": nama_klien, 
        "duration": float(req_duration), 
        "commited_spot": int(req_spot)
    }])
    st.session_state.df_simulasi = pd.concat([st.session_state.df_simulasi, new_row], ignore_index=True)
    
    # Hitung metrik baru dan simpan history
    df_calc, summary_calc = calculate_metrics(st.session_state.df_simulasi)
    sheet_name = f"{st.session_state.sheet_counter}_Book_{nama_klien[:10]}"
    st.session_state.sheets_data[sheet_name] = (df_calc, summary_calc)
    st.session_state.sheet_counter += 1
    
    st.session_state.logs.append(f"📥 Klien '{nama_klien}' masuk (Dur: {req_duration}s, Spot: {req_spot})")
    
    # Cek apakah setelah ditambahkan kuota jadi persis 0
    sisa_sekarang = sellable_quota - daily_dur_req
    if sisa_sekarang <= 0:
        st.session_state.notif = {"msg": f"✅ {nama_klien} masuk. 🚨 PERINGATAN: Kuota Sekarang PENUH (Batas 10%)!", "icon": "⚠️"}
    else:
        st.session_state.notif = {"msg": f"✅ Klien '{nama_klien}' berhasil ditambahkan ke Playlist!", "icon": "🎉"}
        
    return True # Berhasil

def batal_booking(nama_klien):
    df_sim = st.session_state.df_simulasi
    mask = df_sim['client'] == nama_klien
    
    if not mask.any():
        st.error(f"❌ Klien '{nama_klien}' tidak ditemukan di playlist!")
        return False
        
    idx = df_sim[mask].index[0]
    dur_batal = df_sim.at[idx, 'duration']
    spot_batal = df_sim.at[idx, 'commited_spot']
    
    st.session_state.df_simulasi = df_sim.drop(idx).reset_index(drop=True)
    
    df_calc, summary_calc = calculate_metrics(st.session_state.df_simulasi)
    sheet_name = f"{st.session_state.sheet_counter}_Cancel_{nama_klien[:10]}"
    st.session_state.sheets_data[sheet_name] = (df_calc, summary_calc)
    st.session_state.sheet_counter += 1
    
    st.session_state.logs.append(f"🗑️ Klien '{nama_klien}' dihapus. Kuota {dur_batal}s/{spot_batal}x dikembalikan.")
    st.session_state.notif = {"msg": f"🗑️ Slot milik {nama_klien} dihapus. Kuota dikembalikan.", "icon": "✅"}
    return True

# ==========================================
# 4. TAMPILAN GUI STREAMLIT
# ==========================================
st.set_page_config(page_title="LED Booking System", layout="wide")
st.title("📺 Sistem Booking Slot Iklan LED")
st.markdown("Simulasi *booking* dan rekomendasi kapasitas operasional secara *real-time*.")

if not st.session_state.sistem_siap:
    st.info("Sistem belum berjalan. Klik tombol di bawah untuk memuat data awal.")
    if st.button("🚀 Inisialisasi Sistem"):
        initialize_system()
        st.rerun()
else:
    # --- MUNCULKAN POP-UP NOTIF JIKA ADA ---
    if st.session_state.notif:
        st.toast(st.session_state.notif["msg"], icon=st.session_state.notif["icon"])
        st.session_state.notif = None # Hapus agar tidak muncul terus
        
    # --- HITUNG METRIK VISUAL ---
    df_sim = st.session_state.df_simulasi
    df_calc, summary_calc = calculate_metrics(df_sim)
    
    total_operasional = 18 * 3600
    threshold = 0.10 * total_operasional
    kapasitas_maksimal_jual = total_operasional - threshold
    
    total_detik_terjual = summary_calc['total_filled_operational'].iloc[0]
    sellable_quota = kapasitas_maksimal_jual - total_detik_terjual
    
    if sellable_quota < 0: 
        sellable_quota = 0
        
    persen_terjual = (total_detik_terjual / kapasitas_maksimal_jual) * 100
    if persen_terjual > 100: persen_terjual = 100
    persen_sisa = 100 - persen_terjual

    # --- TAMPILKAN METRIK DI ATAS ---
    st.markdown("---")
    st.subheader("📈 Status Kapasitas LED Saat Ini (Batas Aman 90%)")
    
    st.progress(persen_terjual / 100)
    
    col_m1, col_m2, col_m3 = st.columns(3)
    col_m1.metric("Kuota Durasi Terpakai", f"{persen_terjual:.1f}%", f"{int(total_detik_terjual)} detik")
    col_m2.metric("Sisa Kuota Bisa Dijual", f"{persen_sisa:.1f}%", f"{int(sellable_quota)} detik", delta_color="inverse")
    col_m3.metric("Estimasi Waktu Jual", f"{int(sellable_quota / 60)} Menit", "Siap ditawarkan")
    st.markdown("---")

    # --- TAMPILAN UTAMA ---
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("📋 Rekomendasi Kapasitas per Variasi")
        st.caption("Menunjukkan berapa banyak klien tambahan yang bisa ditampung berdasarkan sisa kuota saat ini.")
        
        durations = [30.0, 15.0, 7.5]
        spots = [540, 270, 135]
        
        rekomendasi_data = []
        for d in durations:
            for s in spots:
                kebutuhan_detik = d * s
                max_klien = int(sellable_quota // kebutuhan_detik) if sellable_quota > 0 else 0
                rekomendasi_data.append({
                    "Durasi Paket": f"{d} Detik",
                    "Commited Spot": f"{s} Kali",
                    "Total Waktu/Hari": f"{kebutuhan_detik} Detik",
                    "Kapasitas Maksimal": f"{max_klien} Klien"
                })
                
        df_rekomendasi = pd.DataFrame(rekomendasi_data)
        st.dataframe(df_rekomendasi, use_container_width=True)
            
        st.subheader("📊 Tabel Playlist Saat Ini")
        st.caption("Daftar klien yang aktif tayang di layar LED.")
        st.dataframe(df_calc, use_container_width=True)
        
    with col2:
        st.subheader("📝 Form Booking Klien")
        with st.form("form_booking"):
            nama_baru = st.text_input("Nama Klien Baru")
            dur_baru = st.selectbox("Pilih Durasi (Detik)", [30.0, 15.0, 7.5])
            spot_baru = st.selectbox("Pilih Commited Spot", [540, 270, 135])
            btn_book = st.form_submit_button("Tambahkan ke Playlist")
            
            # Jika tombol diklik
            if btn_book and nama_baru:
                sukses = booking_slot(nama_baru, dur_baru, spot_baru, sellable_quota)
                # Hanya me-refresh halaman (rerun) JIKA booking berhasil
                # Jika gagal, layar diam dan menampilkan error berwarna merah
                if sukses:
                    st.rerun() 
                
        st.subheader("🗑️ Form Batal Booking")
        with st.form("form_batal"):
            nama_batal = st.text_input("Nama Klien yang Dihapus")
            btn_batal = st.form_submit_button("Hapus dari Playlist")
            if btn_batal and nama_batal:
                sukses = batal_booking(nama_batal)
                if sukses:
                    st.rerun() 
                
        st.subheader("📜 Log Aktivitas")
        for log in reversed(st.session_state.logs[-5:]): 
            st.text(log)
            
        st.subheader("💾 Export ke Excel")
        output = io.BytesIO()
        writer = pd.ExcelWriter(output, engine='xlsxwriter')
        for sheet_name, (df_main, df_summary) in st.session_state.sheets_data.items():
            df_main.to_excel(writer, sheet_name=sheet_name, index=False, startrow=0)
            
            start_row_summary = len(df_main) + 2
            worksheet = writer.sheets[sheet_name]
            worksheet.write_string(start_row_summary, 0, '--- SUMMARY METRICS ---')
            df_summary.to_excel(writer, sheet_name=sheet_name, index=False, startrow=start_row_summary + 1)
        writer.close()
        
        st.download_button(
            label="Download Laporan Excel",
            data=output.getvalue(),
            file_name="Riwayat_Booking_LED.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
