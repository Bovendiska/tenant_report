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

@st.cache_data(ttl=600)
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
        return pd.DataFrame()

def submit_sales_log(sales_data):
    """Mengirim data log penjualan (bisa beberapa baris) ke Google Sheets."""
    try:
        creds = Credentials.from_service_account_info(
            st.secrets.to_dict(), scopes=SCOPES
        )
        client = gspread.authorize(creds)
        gsheet = client.open(st.secrets["gsheet_name"])
        worksheet = gsheet.worksheet(st.secrets["log_sheet_name"])
        worksheet.append_rows(sales_data, value_input_option='USER_ENTERED')
        return True, "Transaksi berhasil disimpan!"
    except Exception as e:
        return False, f"Gagal menyimpan transaksi: {e}"

# --- TAMPILAN APLIKASI STREAMLIT ---

st.set_page_config(layout="wide", page_title="Aplikasi Kasir")
st.title("🛒 Aplikasi Kasir Penjualan Tenant")

master_df = load_master_data()

if master_df.empty:
    st.error("Data produk tidak dapat dimuat. Periksa koneksi atau konfigurasi secrets.")
else:
    list_tenant = master_df['nama_tenant'].unique().tolist()
    selected_tenant = st.selectbox("Pilih Tenant:", list_tenant, index=None, placeholder="--Pilih nama tenant--")

    if selected_tenant:
        st.markdown(f"### Menu untuk: **{selected_tenant}**")
        
        products_df = master_df[master_df['nama_tenant'] == selected_tenant]
        transaction_cart = []
        grand_total = 0

        # Membuat header tabel manual
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

        for index, row in products_df.iterrows():
            product_name = row['nama_produk']
            # Harga dari GSheet sekarang menjadi harga default
            default_price = row['harga_jual']
            
            col1, col2, col3, col4 = st.columns([3, 2, 1, 2])
            
            with col1:
                st.write(product_name)

            # --- PERUBAHAN DI SINI ---
            with col2:
                # Mengganti teks statis dengan input angka yang bisa diedit
                # Nilai defaultnya adalah harga dari Google Sheet
                manual_price = st.number_input(
                    "Harga Satuan", 
                    min_value=0, 
                    value=default_price, 
                    key=f"price_{product_name.replace(' ', '_')}",
                    label_visibility="collapsed" # Menyembunyikan label "Harga Satuan"
                )
            
            with col3:
                quantity = st.number_input(
                    "Jumlah", 
                    min_value=0, 
                    step=1, 
                    key=f"qty_{product_name.replace(' ', '_')}",
                    label_visibility="collapsed"
                )
            
            # Subtotal sekarang dihitung dari harga manual
            subtotal = quantity * manual_price
            with col4:
                st.write(f"**{subtotal:,}**")
            # --- AKHIR PERUBAHAN ---

            if quantity > 0:
                grand_total += subtotal
                # Menyimpan harga manual ke dalam log
                transaction_cart.append([
                    selected_tenant,
                    product_name,
                    quantity,
                    manual_price, # <-- Menggunakan harga manual
                    subtotal,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ])
        
        st.divider()
        st.markdown(f"## Total Belanja: Rp {grand_total:,}")
        
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