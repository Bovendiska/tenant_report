import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- KONFIGURASI DAN OTENTIKASI ---

# Mendefinisikan cakupan (izin) yang dibutuhkan untuk mengakses Google Sheets dan Drive
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Menggunakan cache agar data master tidak di-load ulang setiap kali ada interaksi
# Data akan di-cache selama 10 menit (600 detik)
@st.cache_data(ttl=600)
def load_master_data():
    """Memuat data master produk dari Google Sheets dan mengembalikannya sebagai DataFrame."""
    try:
        # Mengambil kredensial dari Streamlit Secrets dan mengotorisasi
        creds = Credentials.from_service_account_info(
            st.secrets.to_dict(), scopes=SCOPES
        )
        client = gspread.authorize(creds)
        
        # Membuka spreadsheet dan worksheet berdasarkan nama dari secrets
        gsheet = client.open(st.secrets["gsheet_name"])
        worksheet = gsheet.worksheet(st.secrets["master_sheet_name"])
        
        # Mengambil semua data dan mengubahnya menjadi DataFrame Pandas
        records = worksheet.get_all_records()
        df = pd.DataFrame(records)
        df['Harga_Jual'] = pd.to_numeric(df['Harga_Jual'], errors='coerce').fillna(0)
        return df
    except Exception as e:
        # Menampilkan pesan error jika gagal memuat data
        st.error(f"Gagal memuat data master: {e}")
        return pd.DataFrame() # Mengembalikan DataFrame kosong jika gagal

def submit_sales_log(sales_data):
    """Mengirim data log penjualan (bisa beberapa baris sekaligus) ke Google Sheets."""
    try:
        creds = Credentials.from_service_account_info(
            st.secrets.to_dict(), scopes=SCOPES
        )
        client = gspread.authorize(creds)
        gsheet = client.open(st.secrets["gsheet_name"])
        worksheet = gsheet.worksheet(st.secrets["log_sheet_name"])
        
        # Menggunakan append_rows untuk efisiensi saat mengirim banyak baris data
        worksheet.append_rows(sales_data, value_input_option='USER_ENTERED')
        
        return True, "Transaksi berhasil disimpan!"
    except Exception as e:
        return False, f"Gagal menyimpan transaksi: {e}"

# --- TAMPILAN UTAMA APLIKASI STREAMLIT ---

# Mengatur konfigurasi halaman
st.set_page_config(layout="wide", page_title="Aplikasi Kasir")
st.title("🛒 Aplikasi Kasir Penjualan Tenant")

# Memuat data master produk
master_df = load_master_data()

# Hanya tampilkan aplikasi jika data master berhasil dimuat
if master_df.empty:
    st.error("Data produk tidak dapat dimuat. Periksa koneksi atau konfigurasi secrets Anda.")
else:
    # --- UI APLIKASI ---
    
    # 1. Widget untuk memilih Tenant
    list_tenant = master_df['Tenant'].unique().tolist()
    selected_tenant = st.selectbox("Pilih Tenant:", list_tenant, index=None, placeholder="--Pilih nama tenant--")

    # Tampilkan daftar produk hanya jika seorang tenant sudah dipilih
    if selected_tenant:
        st.markdown(f"### Menu untuk: **{selected_tenant}**")
        
        # Filter DataFrame untuk mendapatkan produk dari tenant yang dipilih
        products_df = master_df[master_df['Tenant'] == selected_tenant]

        # Inisialisasi keranjang belanja dan total harga
        transaction_cart = []
        grand_total = 0

        # Membuat header tabel secara manual untuk kejelasan
        col1, col2, col3, col4 = st.columns([3, 2, 1, 2])
        with col1:
            st.markdown("**Produk**")
        with col2:
            st.markdown("**Harga Satuan (Rp)**")
        with col3:
            st.markdown("**Jumlah**")
        with col4:
            st.markdown("**Subtotal (Rp)**")
        st.divider()

        # 2. Looping untuk menampilkan setiap produk
        for index, row in products_df.iterrows():
            product_name = row['Produk']
            # Harga dari Google Sheet digunakan sebagai harga default
            default_price = row['Harga_Jual']
            
            col1, col2, col3, col4 = st.columns([3, 2, 1, 2])
            
            with col1:
                st.write(product_name)

            with col2:
                # Input manual untuk harga, dengan nilai default dari GSheet
                manual_price = st.number_input(
                    "Harga Satuan", 
                    min_value=0, 
                    value=default_price, 
                    key=f"price_{product_name.replace(' ', '_')}",
                    label_visibility="collapsed" # Menyembunyikan label agar UI lebih rapi
                )
            
            with col3:
                # Input jumlah dengan tombol + dan -
                quantity = st.number_input(
                    "Jumlah", 
                    min_value=0, 
                    step=1, 
                    key=f"qty_{product_name.replace(' ', '_')}",
                    label_visibility="collapsed"
                )
            
            # 3. Menghitung subtotal secara otomatis
            subtotal = quantity * manual_price
            with col4:
                st.write(f"**{subtotal:,}**")

            # Jika jumlah lebih dari 0, tambahkan item ke keranjang belanja
            if quantity > 0:
                grand_total += subtotal
                transaction_cart.append([
                    selected_tenant,
                    product_name,
                    quantity,
                    manual_price,
                    subtotal,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ])
        
        st.divider()
        # Menampilkan total belanja keseluruhan
        st.markdown(f"## Total Belanja: Rp {grand_total:,}")
        
        # 4. Tombol untuk menyimpan transaksi
        if st.button("Simpan Transaksi", type="primary"):
            if not transaction_cart:
                st.warning("Keranjang masih kosong. Mohon masukkan jumlah produk yang dibeli.")
            else:
                with st.spinner("Menyimpan transaksi..."):
                    success, message = submit_sales_log(transaction_cart)
                
                if success:
                    st.success(message)
                    st.balloons() # Efek balon sebagai konfirmasi
                else:
                    st.error(message)