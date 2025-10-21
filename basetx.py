from web3 import Web3
import os
import time
import decimal
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Konfigurasi
BASE_RPC_URL = "https://mainnet.base.org"
CONTRACT_ADDRESS = "0x4200000000000000000000000000000000000006"
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
ACCOUNT_ADDRESS = os.getenv("ACCOUNT_ADDRESS")

# Validasi environment variables
if not PRIVATE_KEY or not ACCOUNT_ADDRESS:
    print("Error: PRIVATE_KEY atau ACCOUNT_ADDRESS tidak ditemukan di file .env")
    exit(1)

# ABI lengkap untuk WETH contract
WETH_ABI = [
    {
        "name": "deposit",
        "type": "function",
        "stateMutability": "payable",
        "inputs": [],
        "outputs": []
    },
    {
        "name": "withdraw",
        "type": "function", 
        "stateMutability": "nonpayable",
        "inputs": [{"name": "wad", "type": "uint256"}],
        "outputs": []
    },
    {
        "name": "balanceOf",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "account", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}]
    }
]

try:
    w3 = Web3(Web3.HTTPProvider(BASE_RPC_URL))
    if not w3.is_connected():
        print("❌ Gagal terhubung ke jaringan Base")
        exit(1)
    print("✅ Terhubung ke jaringan Base")
except Exception as e:
    print(f"❌ Error koneksi: {e}")
    exit(1)

weth_contract = w3.eth.contract(
    address=Web3.to_checksum_address(CONTRACT_ADDRESS),
    abi=WETH_ABI
)

def get_balances():
    """Mendapatkan balance ETH dan WETH dengan konversi ke float"""
    eth_balance = w3.eth.get_balance(ACCOUNT_ADDRESS)
    weth_balance = weth_contract.functions.balanceOf(ACCOUNT_ADDRESS).call()
    
    # Konversi ke float untuk menghindari masalah decimal.Decimal
    return {
        'eth': float(w3.from_wei(eth_balance, 'ether')),
        'weth': float(w3.from_wei(weth_balance, 'ether'))
    }

def convert_to_float(value):
    """Konversi value ke float dengan aman"""
    if isinstance(value, decimal.Decimal):
        return float(value)
    return float(value)

def swap_eth_to_weth(amount_eth):
    """Swap ETH ke WETH (Wrap)"""
    try:
        amount_eth_float = convert_to_float(amount_eth)
        amount_wei = w3.to_wei(amount_eth_float, 'ether')
        
        balances = get_balances()
        print(f"💰 Saldo ETH: {balances['eth']:.6f} ETH, WETH: {balances['weth']:.6f} WETH")
        
        if balances['eth'] < amount_eth_float:
            print(f"❌ Saldo ETH tidak cukup. Diperlukan: {amount_eth_float} ETH")
            return False

        try:
            gas_estimate = weth_contract.functions.deposit().estimate_gas({
                'from': ACCOUNT_ADDRESS,
                'value': amount_wei
            })
        except Exception as gas_error:
            print(f"❌ Error estimasi gas: {gas_error}")
            return False

        gas_price = w3.eth.gas_price
        gas_cost = gas_estimate * gas_price
        gas_cost_eth = float(w3.from_wei(gas_cost, 'ether'))
        
        print(f"⛽ Estimasi gas: {gas_estimate}")
        print(f"💸 Biaya gas: {gas_cost_eth:.8f} ETH")
        
        if balances['eth'] < (amount_eth_float + gas_cost_eth):
            print("❌ Saldo tidak cukup untuk amount + gas fee")
            return False

        transaction = weth_contract.functions.deposit().build_transaction({
            'from': ACCOUNT_ADDRESS,
            'value': amount_wei,
            'gas': int(gas_estimate * 1.2),
            'gasPrice': gas_price,
            'nonce': w3.eth.get_transaction_count(ACCOUNT_ADDRESS),
            'chainId': 8453
        })

        signed_txn = w3.eth.account.sign_transaction(transaction, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
        
        print(f"📤 Transaction sent: https://basescan.org/tx/{tx_hash.hex()}")
        print("⏳ Menunggu konfirmasi...")

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        
        if receipt.status == 1:
            print("✅ Swap ETH → WETH berhasil!")
            new_balances = get_balances()
            print(f"✅ Saldo baru - ETH: {new_balances['eth']:.6f}, WETH: {new_balances['weth']:.6f}")
            return True
        else:
            print("❌ Swap ETH → WETH gagal!")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def swap_weth_to_eth(amount_weth):
    """Swap WETH ke ETH (Unwrap)"""
    try:
        amount_weth_float = convert_to_float(amount_weth)
        amount_wei = w3.to_wei(amount_weth_float, 'ether')
        
        balances = get_balances()
        print(f"💰 Saldo ETH: {balances['eth']:.6f} ETH, WETH: {balances['weth']:.6f} WETH")
        
        if balances['weth'] < amount_weth_float:
            print(f"❌ Saldo WETH tidak cukup. Diperlukan: {amount_weth_float} WETH")
            return False

        try:
            gas_estimate = weth_contract.functions.withdraw(amount_wei).estimate_gas({
                'from': ACCOUNT_ADDRESS
            })
        except Exception as gas_error:
            print(f"❌ Error estimasi gas: {gas_error}")
            return False

        gas_price = w3.eth.gas_price
        gas_cost = gas_estimate * gas_price
        gas_cost_eth = float(w3.from_wei(gas_cost, 'ether'))
        
        if balances['eth'] < gas_cost_eth:
            print("❌ Saldo ETH tidak cukup untuk gas fee")
            return False

        print(f"⛽ Estimasi gas: {gas_estimate}")
        print(f"💸 Biaya gas: {gas_cost_eth:.8f} ETH")

        transaction = weth_contract.functions.withdraw(amount_wei).build_transaction({
            'from': ACCOUNT_ADDRESS,
            'gas': int(gas_estimate * 1.2),
            'gasPrice': gas_price,
            'nonce': w3.eth.get_transaction_count(ACCOUNT_ADDRESS),
            'chainId': 8453
        })

        signed_txn = w3.eth.account.sign_transaction(transaction, PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
        
        print(f"📤 Transaction sent: https://basescan.org/tx/{tx_hash.hex()}")
        print("⏳ Menunggu konfirmasi...")

        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
        
        if receipt.status == 1:
            print("✅ Swap WETH → ETH berhasil!")
            new_balances = get_balances()
            print(f"✅ Saldo baru - ETH: {new_balances['eth']:.6f}, WETH: {new_balances['weth']:.6f}")
            return True
        else:
            print("❌ Swap WETH → ETH gagal!")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

def auto_swap_loop():
    """Loop otomatis untuk swap bolak-balik"""
    print("\n" + "="*50)
    print("🤖 BOT AUTO SWAP ETH ⇄ WETH")
    print("="*50)
    
    try:
        swap_amount = float(input("Masukkan jumlah untuk setiap swap: "))
        delay_seconds = float(input("Masukkan delay antara swap (detik): "))
        mode = input("Pilih mode (1: ETH→WETH, 2: WETH→ETH, 3: Bolak-balik): ")
    except ValueError:
        print("❌ Input tidak valid. Pastikan memasukkan angka.")
        return
    
    print(f"\n⚙️  Konfigurasi:")
    print(f"   Amount: {swap_amount}")
    print(f"   Delay: {delay_seconds} detik")
    print(f"   Mode: {mode}")
    print("🛑 Tekan Ctrl+C untuk menghentikan bot")
    print("="*50)
    
    counter = 0
    
    try:
        while True:
            counter += 1
            print(f"\n🔄 Iterasi #{counter} - {time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            balances = get_balances()
            print(f"💰 Saldo saat ini - ETH: {balances['eth']:.6f}, WETH: {balances['weth']:.6f}")
            
            if mode == "1":  # Hanya ETH → WETH
                if balances['eth'] > swap_amount:
                    success = swap_eth_to_weth(swap_amount)
                    if not success:
                        print("⏳ Swap gagal, menunggu sebelum mencoba lagi...")
                else:
                    print("❌ Saldo ETH tidak cukup, menunggu...")
            
            elif mode == "2":  # Hanya WETH → ETH
                if balances['weth'] > swap_amount:
                    success = swap_weth_to_eth(swap_amount)
                    if not success:
                        print("⏳ Swap gagal, menunggu sebelum mencoba lagi...")
                else:
                    print("❌ Saldo WETH tidak cukup, menunggu...")
            
            elif mode == "3":  # Bolak-balik
                if counter % 2 == 1:  # Ganjil: ETH → WETH
                    if balances['eth'] > swap_amount:
                        success = swap_eth_to_weth(swap_amount)
                        if not success:
                            print("⏳ Swap gagal, mencoba mode sebaliknya...")
                            if balances['weth'] > swap_amount:
                                swap_weth_to_eth(swap_amount)
                    else:
                        print("❌ Saldo ETH tidak cukup, mencoba WETH → ETH...")
                        if balances['weth'] > swap_amount:
                            swap_weth_to_eth(swap_amount)
                else:  # Genap: WETH → ETH
                    if balances['weth'] > swap_amount:
                        success = swap_weth_to_eth(swap_amount)
                        if not success:
                            print("⏳ Swap gagal, mencoba mode sebaliknya...")
                            if balances['eth'] > swap_amount:
                                swap_eth_to_weth(swap_amount)
                    else:
                        print("❌ Saldo WETH tidak cukup, mencoba ETH → WETH...")
                        if balances['eth'] > swap_amount:
                            swap_eth_to_weth(swap_amount)
            else:
                print("❌ Mode tidak valid, menggunakan mode bolak-balik (3)")
                mode = "3"
            
            print(f"⏰ Menunggu {delay_seconds} detik sebelum swap berikutnya...")
            time.sleep(delay_seconds)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Bot dihentikan oleh user")
        print("Terima kasih telah menggunakan auto swap bot!")
    except Exception as e:
        print(f"❌ Error dalam loop: {e}")

def manual_swap():
    """Mode manual untuk single swap"""
    print("\n" + "="*50)
    print("🔧 MODE MANUAL SWAP")
    print("="*50)
    
    balances = get_balances()
    print(f"💰 Saldo saat ini - ETH: {balances['eth']:.6f}, WETH: {balances['weth']:.6f}")
    
    direction = input("Pilih arah swap (1: ETH→WETH, 2: WETH→ETH): ")
    try:
        amount = float(input("Masukkan jumlah: "))
    except ValueError:
        print("❌ Jumlah harus angka")
        return
    
    if direction == "1":
        swap_eth_to_weth(amount)
    elif direction == "2":
        swap_weth_to_eth(amount)
    else:
        print("❌ Pilihan tidak valid")

if __name__ == "__main__":
    try:
        while True:
            print("\n" + "="*50)
            print("🤖 BOT SWAP ETH/WETH BASE NETWORK")
            print("="*50)
            print("1. Auto Swap Mode (Loop terus menerus)")
            print("2. Manual Swap Mode (Satu kali)")
            print("3. Cek Balance")
            print("4. Keluar")
            
            choice = input("\nPilih mode (1-4): ")
            
            if choice == "1":
                auto_swap_loop()
            elif choice == "2":
                manual_swap()
            elif choice == "3":
                balances = get_balances()
                print(f"\n💰 Saldo saat ini:")
                print(f"   ETH: {balances['eth']:.6f}")
                print(f"   WETH: {balances['weth']:.6f}")
            elif choice == "4":
                print("👋 Sampai jumpa!")
                break
            else:
                print("❌ Pilihan tidak valid")
                
    except KeyboardInterrupt:
        print("\n\n👋 Program dihentikan")