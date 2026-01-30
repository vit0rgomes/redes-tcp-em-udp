import random
import socket
import json
import time
import csv
import matplotlib.pyplot as plt
import numpy as np

# ======================================================================================
# Configuração
# ======================================================================================

localIP     = "127.0.0.1"
local_port  = 20001
buffer_size = 1024
ISN         = 5000
nbr_of_pct  = 10000

initial_cwnd = 1.0
initial_ssthresh = 64
max_cwnd = 100
timeout = 2.0
duplicate_ack_threshold = 3
LOSS_RATE = 0.005

pct_zero = {'seq': 0, 
            'ack': 0, 
            'rwnd': 1024, 
            'SYN': False, 
            'FIN': False, 
            'payload': ""
            }

# ======================================================================================
# Funções Auxiliares
# ======================================================================================

def caesar_cipher(text, shift=3):
    result = ""
    for char in text:
        if 'a' <= char <= 'z':
            result += chr((ord(char) - ord('a') + shift) % 26 + ord('a'))
        elif 'A' <= char <= 'Z':
            result += chr((ord(char) - ord('A') + shift) % 26 + ord('A'))
        else:
            result += char
    return result

def caesar_decipher(text, shift=3):
    return caesar_cipher(text, -shift)

def my_encode_and_send(socket, msg, adress_port):
    msg_copy = msg.copy()
    if msg_copy.get('payload'):
        msg_copy['payload'] = caesar_cipher(msg_copy['payload'])
    socket.sendto(json.dumps(msg_copy).encode('utf-8'), adress_port)

def my_receive_and_decode(socket, buffer_size):
    pct, address = socket.recvfrom(buffer_size)
    msg = json.loads(pct.decode('utf-8'))
    if msg.get('payload'):
        msg['payload'] = caesar_decipher(msg['payload'])
    return msg, address

# ======================================================================================
# Handshake
# ======================================================================================

def initConnection(IP, port, pct, buffer_size, ISN, timeout=2.0):
    print("Subindo Servidor UDP e escutando...\n")
    
    UDPServerSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    UDPServerSocket.bind((IP, port))

    print(f"   {'Cliente':<47} {'Servidor'}")
    print(f"   |{' '*46}|")

    # 1ª via
    syn1_msg, address = my_receive_and_decode(UDPServerSocket, buffer_size)
    print(f"   |───── SYN (seq={syn1_msg['seq']}){' '*13} ────▶|")
    
    UDPServerSocket.settimeout(timeout)

    while True:
        try:
            # 2ª via
            syn2_ack_msg = pct.copy()
            syn2_ack_msg.update({'SYN': True, 'ack': syn1_msg['seq'] + 1, 'seq': ISN})
            seq_esperado = syn2_ack_msg['ack']
            
            print(f"   |◀────── SYN-ACK (seq={ISN}, ack={seq_esperado}){' '*1} ───────|")
            my_encode_and_send(UDPServerSocket, syn2_ack_msg, address)
            
            # 3ª via
            syn3_ack_msg, _ = my_receive_and_decode(UDPServerSocket, buffer_size)
            now_ack = syn3_ack_msg['ack']
            
            print(f"   |───── ACK (seq={syn3_ack_msg['seq']}, ack={now_ack}){' '*6} ────▶|")
            print(f"   |{' '*46}|")
            print(f"   └──────────── CONEXÃO ESTABELECIDA ─────────────┘")
            
            if seq_esperado == syn3_ack_msg['seq']:
                break
            
        except socket.timeout:
            print("[!] Timeout! Reenviando...")
    
    return UDPServerSocket, address, now_ack

# ======================================================================================
# Controle de Congestionamento - CORRIGIDO PARA DOBRAR NO SLOW START
# ======================================================================================

def get_window_size(cwnd, rwnd):
    return min(cwnd, rwnd)

def handle_new_ack(cwnd, ssthresh, num_packets, in_fast_recovery):
    """
    CORRIGIDO: Agora implementa corretamente o comportamento de dobrar no Slow Start
    
    - Slow Start: aumenta cwnd em 1 para CADA pacote confirmado → janela DOBRA a cada RTT
    - Congestion Avoidance: aumenta cwnd em 1/cwnd para cada pacote → cresce linearmente
    """
    if in_fast_recovery:
        # Sai do Fast Recovery para Congestion Avoidance
        new_cwnd = ssthresh
        print(f"   [FR→CA] CWND: {cwnd:.1f} → {new_cwnd:.1f}, SSThresh: {ssthresh}")
        return new_cwnd, ssthresh, False, 0
    
    elif cwnd < ssthresh:
        # SLOW START: incrementa cwnd em 1 para CADA pacote confirmado
        # Isso faz a janela DOBRAR a cada RTT
        increment = num_packets  # Cada pacote confirmado adiciona 1 ao CWND
        new_cwnd = min(cwnd + increment, max_cwnd)
        
        print(f"   [SLOW START] CWND: {cwnd:.1f} + {increment} = {new_cwnd:.1f} (SSThresh: {ssthresh})")
        
        return new_cwnd, ssthresh, False, 0
    
    else:
        # CONGESTION AVOIDANCE: aumenta ~1 MSS por RTT
        # Incrementa 1/cwnd para cada pacote confirmado
        increment = num_packets / cwnd
        new_cwnd = min(cwnd + increment, max_cwnd)
        
        print(f"   [CONG AVOID] CWND: {cwnd:.1f} + {increment:.2f} = {new_cwnd:.1f} (SSThresh: {ssthresh})")
        
        return new_cwnd, ssthresh, False, 0

def handle_duplicate_ack(cwnd, ssthresh, duplicate_acks, in_fast_recovery):
    duplicate_acks += 1
    should_retransmit = False

    if duplicate_acks == duplicate_ack_threshold and not in_fast_recovery:
        cwnd = max(cwnd / 2, 2)
        in_fast_recovery = True
        should_retransmit = True
        
        print(f"\n{'!'*40}")
        print(f"  FAST RETRANSMIT - CWND: {cwnd:.1f}, SSThresh: {ssthresh}")
        print(f"{'!'*40}\n")

    elif in_fast_recovery:
        cwnd = min(cwnd + 1, max_cwnd)

    return cwnd, ssthresh, duplicate_acks, in_fast_recovery, should_retransmit

def handle_timeout(cwnd, ssthresh):
    new_ssthresh = max(int(cwnd / 2), 2)
    print(f"\n{'!'*60}")
    print(f"  TIMEOUT - CWND: {cwnd:.1f} → {initial_cwnd}, SSThresh: {ssthresh} → {new_ssthresh}")
    print(f"{'!'*60}\n")
    
    return initial_cwnd, new_ssthresh, False, 0

# ======================================================================================
# Envio de Mensagens - COM LOGS MOSTRANDO CRESCIMENTO EXPONENCIAL
# ======================================================================================

def send_messages(sock, addr, start_seq, total_msgs):
    cwnd, ssthresh, duplicate_acks, in_fast_recovery = initial_cwnd, initial_ssthresh, 0, False
    next_msg, base_seq, current_seq = 0, start_seq, start_seq
    in_flight, retransmissions, last_rwnd = {}, 0, 1024

    # Dados para gráficos
    cwnd_data = [[0.0, cwnd, ssthresh]]
    throughput_data = []  # [(tempo, mensagens_enviadas_acumuladas)]
    retrans_data = []  # [(tempo, total_retransmissões)]
    
    start_time = time.time()
    last_throughput_time = start_time
    messages_sent_total = 0
    
    sock.settimeout(0.5)
    
    print(f"\n{'='*70}")
    print(f"INICIANDO TRANSMISSÃO - CWND inicial: {cwnd}, SSThresh: {ssthresh}")
    print(f"{'='*70}")
    print(f"⚡ NO SLOW START: CWND DOBRA A CADA RTT (1→2→4→8...)")
    print(f"{'='*70}\n")
    
    round_num = 0
    packets_this_round = 0
    
    while base_seq < current_seq or next_msg < total_msgs:
        window_size = get_window_size(cwnd, last_rwnd)
        
        # Log do início da rodada
        if packets_this_round == 0:
            round_num += 1
            print(f"\n{'─'*70}")
            print(f" RODADA {round_num}")
            print(f"   CWND: {cwnd:.1f} pacotes | Window: {window_size:.1f} | Em voo: {len(in_flight)}")
            print(f"{'─'*70}")
        
        # Envio inicial
        sent_this_iteration = 0
        while len(in_flight) < window_size and next_msg < total_msgs:
            payload = f"Mensagem numero {next_msg}"
            payload_size = len(caesar_cipher(payload).encode('utf-8'))
            
            pct = pct_zero.copy()
            pct['seq'], pct['payload'] = current_seq, payload
            
            if random.random() < LOSS_RATE:
                print(f"   |<--X--- [PERDIDO] seq={current_seq} ---X-->|")
            else:
                my_encode_and_send(sock, pct, addr)
                print(f"   |◀─────── DADOS (seq={current_seq}){' '*(30-len(str(current_seq))-12)} ───────| (Msg {next_msg})")
            
            in_flight[current_seq] = (next_msg, payload, time.time())
            current_seq += payload_size
            next_msg += 1
            sent_this_iteration += 1
            packets_this_round += 1
            messages_sent_total += 1
            
            # Registra throughput a cada segundo
            current_time = time.time()
            if current_time - last_throughput_time >= 1.0:
                throughput_data.append([current_time - start_time, messages_sent_total])
                last_throughput_time = current_time

        if sent_this_iteration > 0:
            print(f"    Enviados {sent_this_iteration} pacote(s) nesta iteração")

        # Recebe ACKs
        try:
            ack_msg, _ = my_receive_and_decode(sock, buffer_size)
            received_ack = ack_msg['ack']
            last_rwnd = ack_msg.get('rwnd', 1024)
            
            if received_ack > base_seq:
                # ACK novo
                confirmed = [s for s in in_flight if s < received_ack]
                num_confirmed = len(confirmed)
                
                print(f"   |───── ACK (ack={received_ack}){' '*(30-len(str(received_ack))-10)} ────▶| ✓ {num_confirmed} pct(s) confirmado(s)")
                
                for seq in confirmed:
                    del in_flight[seq]
                
                old_cwnd = cwnd
                cwnd, ssthresh, in_fast_recovery, duplicate_acks = handle_new_ack(
                    cwnd, ssthresh, num_confirmed, in_fast_recovery)
                
                if old_cwnd != cwnd:
                    cwnd_data.append([time.time() - start_time, cwnd, ssthresh])
                
                base_seq = received_ack
                packets_this_round = 0  # Nova rodada começa
                
            elif received_ack == base_seq and in_flight:
                # ACK duplicado
                print(f"   |───── ACK (ack={received_ack}){' '*(30-len(str(received_ack))-10)} ────▶| ⚠️ Duplicado #{duplicate_acks+1}")
                
                cwnd, ssthresh, duplicate_acks, in_fast_recovery, should_retransmit = handle_duplicate_ack(
                    cwnd, ssthresh, duplicate_acks, in_fast_recovery)
                
                if should_retransmit and in_flight:
                    retrans_seq = min(in_flight.keys())
                    msg_num, payload, _ = in_flight[retrans_seq]
                    
                    pct = pct_zero.copy()
                    pct['seq'], pct['payload'] = retrans_seq, payload
                    
                    my_encode_and_send(sock, pct, addr)
                    in_flight[retrans_seq] = (msg_num, payload, time.time())
                    retransmissions += 1
                    
                    print(f"   |◀───────  RETRANS (seq={retrans_seq}){' '*(30-len(str(retrans_seq))-14)} ───────|")
                    cwnd_data.append([time.time() - start_time, cwnd, ssthresh])
                    retrans_data.append([time.time() - start_time, retransmissions])
            
            elif received_ack < base_seq:
                print(f"   |───── ACK (ack={received_ack}){' '*(30-len(str(received_ack))-10)} ────▶| (Antigo)")

        except socket.timeout:
            current_time = time.time()
            
            for seq in sorted(in_flight.keys()):
                msg_num, payload, timestamp = in_flight[seq]
                
                if current_time - timestamp > timeout:
                    cwnd, ssthresh, in_fast_recovery, duplicate_acks = handle_timeout(cwnd, ssthresh)
                    
                    pct = pct_zero.copy()
                    pct['seq'], pct['payload'] = seq, payload
                    
                    my_encode_and_send(sock, pct, addr)
                    in_flight[seq] = (msg_num, payload, current_time)
                    retransmissions += 1
                    
                    print(f"   |◀───────  TIMEOUT RE-TX (seq={seq}){' '*(30-len(str(seq))-18)} ───────|")
                    cwnd_data.append([time.time() - start_time, cwnd, ssthresh])
                    retrans_data.append([time.time() - start_time, retransmissions])
                    packets_this_round = 0
                    break
    
    # Adiciona último ponto de throughput
    throughput_data.append([time.time() - start_time, messages_sent_total])
    
    # Estatísticas
    total_sent = next_msg
    efficiency = (total_msgs / total_sent * 100) if total_sent > 0 else 0

    print(f"\n{'='*70}")
    print(f"✅ TRANSMISSÃO COMPLETA!")
    print(f"{'='*70}")
    print(f"Mensagens únicas: {total_msgs}")
    print(f"Total enviado: {total_sent}")
    print(f"Retransmissões: {retransmissions} ({100*retransmissions/total_sent:.2f}%)")
    print(f"Eficiência: {efficiency:.1f}%")
    print(f"CWND final: {cwnd:.1f}, SSThresh: {ssthresh}")
    print(f"{'='*70}\n")
    
    # Salva CSV
    try:
        with open('congestion_data.csv', 'w', newline='') as f:
            csv.writer(f).writerows([['Time', 'CWND', 'SSThresh']] + cwnd_data)
        print(" Dados salvos em 'congestion_data.csv'")
    except IOError as e:
        print(f"Erro ao salvar CSV: {e}")

    return current_seq, cwnd_data, throughput_data, retrans_data, {
        'total_msgs': total_msgs,
        'total_sent': total_sent,
        'retransmissions': retransmissions,
        'efficiency': efficiency
    }

# ======================================================================================
# Finalização
# ======================================================================================

def finishConnection(socket, address, now_ack):
    fin_pct = pct_zero.copy()
    fin_pct.update({'seq': now_ack, 'FIN': True, 'payload': ''})
    
    socket.settimeout(2.0)
    print(f"   |{' '*46}|")
    
    my_encode_and_send(socket, fin_pct, address)
    print(f"   |◀─────── FIN (seq={now_ack}){' '*(30-len(str(now_ack))-10)} ───────|")
    
    for _ in range(5):
        try:
            fin_ack_msg, _ = my_receive_and_decode(socket, buffer_size)
            
            if fin_ack_msg['ack'] == now_ack + 1:
                print(f"   |───── FIN-ACK (ack={fin_ack_msg['ack']}){' '*(30-len(str(fin_ack_msg['ack']))-15)} ────▶|")
                
                last_ack_pct = pct_zero.copy()
                last_ack_pct['ack'] = fin_ack_msg['seq'] + 1
                my_encode_and_send(socket, last_ack_pct, address)
                
                print(f"   └──────────── CONEXÃO FINALIZADA ──────────────┘")
                break
            
        except socket.timeout:
            print("[!] Timeout! Reenviando FIN...")
            my_encode_and_send(socket, fin_pct, address)
        except Exception as e:
            print(f"Erro: {e}")
            break
            
    socket.close()
    print("Conexão finalizada.")

# ======================================================================================
# Função de Plotagem de Gráficos - VERSÃO MELHORADA E PROFISSIONAL
# ======================================================================================

def plot_transmission_graphs(cwnd_data, throughput_data, retrans_data, stats,
                             initial_cwnd=1,
                             initial_ssthresh=16,
                             loss_rate=0.0,
                             timeout=1.0):
    """
    Plota 3 gráficos:
    1) Evolução do CWND e SSThresh
    2) CWND em escala logarítmica
    3) Painel de estatísticas da transmissão TCP
    """

    import matplotlib.pyplot as plt
    import numpy as np

    plt.style.use('seaborn-v0_8-darkgrid')
    fig = plt.figure(figsize=(20, 12))
    fig.patch.set_facecolor('#f8f9fa')

    fig.suptitle(
        'Análise Completa de Transmissão TCP com Controle de Congestionamento',
        fontsize=18, fontweight='bold', y=0.98
    )

    gs = fig.add_gridspec(3, 3, hspace=0.35, wspace=0.3)

    # ==================================================================================
    # GRÁFICO 1 — Evolução do CWND e SSThresh
    # ==================================================================================
    ax1 = fig.add_subplot(gs[0, :2])

    times = [t for t, _, _ in cwnd_data]
    cwnds = [c for _, c, _ in cwnd_data]
    ssthreshs = [s for _, _, s in cwnd_data]

    ax1.plot(times, cwnds, label='CWND', linewidth=2.5,
             marker='o', markersize=3, markevery=max(1, len(times)//50))
    ax1.plot(times, ssthreshs, 'r--', linewidth=2,
             label='SSThresh', alpha=0.8)

    ax1.fill_between(times, cwnds, alpha=0.2)

    # Slow Start: cwnd < ssthresh
    slow_start_idx = [i for i, (c, s) in enumerate(zip(cwnds, ssthreshs)) if c < s]
    if slow_start_idx:
        ax1.scatter([times[i] for i in slow_start_idx],
                    [cwnds[i] for i in slow_start_idx],
                    c='green', s=30, alpha=0.5,
                    label='Slow Start', zorder=5)

    # Eventos de congestão: queda de ssthresh
    congestion_events = [
        (times[i], cwnds[i])
        for i in range(1, len(ssthreshs))
        if ssthreshs[i] < ssthreshs[i - 1]
    ]

    if congestion_events:
        t_ce, c_ce = zip(*congestion_events)
        ax1.scatter(t_ce, c_ce, c='red', marker='X', s=100,
                    edgecolors='black', linewidths=1,
                    label='Evento de Congestão', zorder=10)

    # Pico de CWND
    max_cwnd = max(cwnds)
    max_idx = cwnds.index(max_cwnd)
    ax1.annotate(
        f'Pico: {max_cwnd:.1f}',
        xy=(times[max_idx], max_cwnd),
        xytext=(10, 10),
        textcoords='offset points',
        bbox=dict(boxstyle='round', facecolor='yellow', alpha=0.7),
        arrowprops=dict(arrowstyle='->')
    )

    ax1.set_title('Evolução do CWND e SSThresh', fontsize=13, fontweight='bold')
    ax1.set_xlabel('Tempo (s)', fontsize=12)
    ax1.set_ylabel('Janela (pacotes)', fontsize=12)
    ax1.legend()
    ax1.set_facecolor('#ffffff')

    # ==================================================================================
    # GRÁFICO 2 — CWND em Escala Logarítmica
    # ==================================================================================
    ax2 = fig.add_subplot(gs[0, 2])

    ax2.semilogy(times, cwnds, 'b-', linewidth=2,
                 marker='o', markersize=3, label='CWND')
    ax2.semilogy(times, ssthreshs, 'r--', linewidth=2,
                 label='SSThresh', alpha=0.7)

    # Linha de referência exponencial (2^x)
    if len(times) > 1:
        t0, t1 = times[0], times[-1]
        span = max(t1 - t0, 1e-6)

        exp_ref = [
            initial_cwnd * (2 ** ((t - t0) / (span / 6)))
            for t in times
        ]

        ax2.semilogy(times, exp_ref, 'g:',
                     linewidth=1.5, alpha=0.6,
                     label='Referência exponencial (2^x)')

    ax2.set_title('CWND em Escala Logarítmica', fontsize=11, fontweight='bold')
    ax2.set_xlabel('Tempo (s)')
    ax2.set_ylabel('Janela (log)')
    ax2.legend(fontsize=8)
    ax2.set_facecolor('#ffffff')

    # ==================================================================================
    # PAINEL DE ESTATÍSTICAS
    # ==================================================================================
    ax3 = fig.add_subplot(gs[2, 1:])
    ax3.axis('off')

    efficiency = stats.get('efficiency', 0)
    total_sent = stats.get('total_sent', 0)
    retransmissions = stats.get('retransmissions', 0)

    retrans_rate = (100 * retransmissions / total_sent) if total_sent else 0

    stats_text = f"""
╔══════════════════════════════════════════════════════════════╗
║           ESTATÍSTICAS DA TRANSMISSÃO TCP                    ║
╚══════════════════════════════════════════════════════════════╝

 MÉTRICAS:
   • Total Enviado:              {total_sent:>6}
   • Retransmissões:             {retransmissions:>6}
   • Taxa de Retransmissão:      {retrans_rate:>6.2f} %
   • Eficiência:                 {efficiency:>6.1f} %

  CONFIGURAÇÃO:
   • CWND Inicial:               {initial_cwnd:>6.1f}
   • SSThresh Inicial:           {initial_ssthresh:>6.1f}
   • CWND Máximo:                {max_cwnd:>6.1f}
   • Taxa de Perda:              {loss_rate * 100:>6.2f} %
   • Timeout:                    {timeout:>6.2f} s

 ALGORITMO:
   • Slow Start:                 OK (crescimento exponencial)
   • Congestion Avoidance:       OK (crescimento linear)
   • Fast Retransmit/Recovery:   OK
"""

    ax3.text(
        0.05, 0.5, stats_text,
        fontsize=10, family='monospace',
        verticalalignment='center',
        bbox=dict(boxstyle='round,pad=1',
                  facecolor='#e8f5e9',
                  edgecolor='#4CAF50',
                  linewidth=2)
    )

    # ==================================================================================
    # SALVAMENTO
    # ==================================================================================
    plt.savefig('transmission_analysis.png', dpi=200,
                bbox_inches='tight', facecolor='#f8f9fa')
    plt.savefig('transmission_analysis.pdf',
                bbox_inches='tight', facecolor='#f8f9fa')

    plt.show()


# ======================================================================================
# Main
# ======================================================================================

if __name__ == "__main__":
    sock, addr, seq = initConnection(localIP, local_port, pct_zero, buffer_size, ISN)
    final_seq, cwnd_data, throughput_data, retrans_data, stats = send_messages(sock, addr, seq, nbr_of_pct)
    finishConnection(sock, addr, final_seq)
    
    # Plota os gráficos
    print("\n Gerando gráficos de análise...")
    plot_transmission_graphs(cwnd_data, throughput_data, retrans_data, stats)