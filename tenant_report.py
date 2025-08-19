import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- KONFIGURASI DAN OTENTIKASI ---

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Menggunakan cache agar data master tidak di-load ulang setiap kali ada interaksi
@st.cache_data(ttl=600) # Cache data selama 10 menit
def load_master_data():
    """Memuat data master produk dari Google Sheets dan mengembalikannya sebagai DataFrame."""
    try:
        creds = Credentials.from_service_account_info(
            st.secrets.to_dict(), scopes=SCOPES
        )
        client = gspread.authorize(creds)
        gsheet = client.open(st.secrets["gsheet_name"])
        worksheet = gsheet.worksheet(st.secrets["master_sheet_name"])
        records = worksheet.get_all_records()
        df = pd.DataFrame(records)
        return df
    except Exception as e:
        st.error(f"Gagal memuat data master: {e}")
        return pd.DataFrame() # Mengembalikan DataFrame kosong jika gagal

def submit_sales_log(sales_data):
    """Mengirim data log penjualan (bisa beberapa baris) ke Google Sheets."""
    try:
        creds = Credentials.from_service_account_info(
            st.secrets.to_dict(), scopes=SCOPES
        )
        client = gspread.authorize(creds)
        gsheet = client.open(st.secrets["gsheet_name"])
        worksheet = gsheet.worksheet(st.secrets["log_sheet_name"])
        
        # append_rows lebih efisien untuk banyak baris
        worksheet.append_rows(sales_data, value_input_option='USER_ENTERED')
        
        return True, "Transaksi berhasil disimpan!"
    except Exception as e:
        return False, f"Gagal menyimpan transaksi: {e}"

# --- TAMPILAN APLIKASI STREAMLIT ---

st.set_page_config(layout="wide", page_title="Aplikasi Kasir")
st.title("🛒 Aplikasi Kasir Penjualan Tenant")

# Memuat data master
master_df = load_master_data()

if master_df.empty:
    st.error("Data produk tidak dapat dimuat. Periksa koneksi atau konfigurasi secrets.")
else:
    # --- UI APLIKASI ---
    
    # 1. Pilih Tenant
    list_tenant = master_df['Tenant'].unique().tolist()
    selected_tenant = st.selectbox("Pilih Tenant:", list_tenant, index=None, placeholder="--Pilih nama tenant--")

    # Hanya tampilkan daftar produk jika tenant sudah dipilih
    if selected_tenant:
        st.markdown(f"### Menu untuk: **{selected_tenant}**")
        
        # Filter produk untuk tenant yang dipilih
        products_df = master_df[master_df['Tenant'] == selected_tenant]

        # Inisialisasi keranjang belanja dan total
        transaction_cart = []
        grand_total = 0

        # 2. Masukkan Jumlah Produk
        for index, row in products_df.iterrows():
            product_name = row['Produk']
            product_price = row['Harga_Jual']
            
            col1, col2, col3, col4 = st.columns([3, 2, 1, 2])
            
            with col1:
                st.write(product_name)
            with col2:
                manual_price = st.number_input(
                    "Harga Satuan", 
                    min_value=0, 
                    value=[product_price], 
                    key=f"price_{product_name.replace(' ', '_')}",
                    label_visibility="collapsed" # Menyembunyikan label "Harga Satuan"
                )
            with col3:
                # Kotak input jumlah untuk setiap produk
                quantity = st.number_input("Jumlah", min_value=0, step=1, key=f"qty_{product_name.replace(' ', '_')}")
            
            subtotal = quantity * product_price
            with col4:
                st.write(f"Rp {subtotal:}")

            # Jika jumlah lebih dari 0, tambahkan ke keranjang
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
        
        st.markdown("---")
        # 3. Tampilkan Total Harga Otomatis
        st.markdown(f"## Total Belanja: Rp {grand_total:,}")
        
        # 4. Tombol Submit
        if st.button("Simpan Transaksi", type="primary"):
            if not transaction_cart:
                st.warning("Keranjang masih kosong. Mohon masukkan jumlah produk yang dibeli.")
            else:
                with st.spinner("Menyimpan transaksi..."):
                    success, message = submit_sales_log(transaction_cart)
                
                if success:
                    st.success(message)
                    st.balloons()
                else:
                    st.error(message)