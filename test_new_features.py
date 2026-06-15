import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import requests

base = 'http://localhost:8001'

print('='*60)
print('新功能API测试')
print('='*60)

# 测试1: 多频仿真
print('\n[1] 测试多频仿真 (multifrequency)')
payload = {
    'grid_size': 16,
    'edema_regions': [
        {'center_x': 8, 'center_y': 6, 'radius': 2, 'conductivity_factor': 2.0}
    ],
    'drawn_mask': None
}
try:
    resp = requests.post(f'{base}/api/simulation/multifrequency', json=payload, timeout=120)
    if resp.status_code == 200:
        d = resp.json()
        print('  任务ID:', d['task_id'])
        print('  重建频率数量:', len(d['reconstructions']))
        freqs = ['1kHz', '10kHz', '100kHz']
        for f in freqs:
            rec = d['reconstructions'][f]
            b64 = d['reconstructed_images_base64'][f]
            print(f'  {f}: {len(rec)}x{len(rec[0])}, Base64:{len(b64)} chars')
        print('  融合图尺寸:', len(d['fused_reconstruction']), 'x', len(d['fused_reconstruction'][0]))
        print('  Cole-Cole参数:')
        cc = d['cole_cole_params']
        nc = cc['normal_conductivity']
        ec = cc['edema_conductivity']
        print(f'    正常组织: 1kHz={nc["1kHz"]:.4f}, 10kHz={nc["10kHz"]:.4f}, 100kHz={nc["100kHz"]:.4f} S/m')
        print(f'    水肿组织: 1kHz={ec["1kHz"]:.4f}, 10kHz={ec["10kHz"]:.4f}, 100kHz={ec["100kHz"]:.4f} S/m')
        print('  ✓ 多频仿真测试通过!')
    else:
        print('  失败:', resp.status_code, resp.text[:200])
except Exception as e:
    import traceback
    traceback.print_exc()
    print('  错误:', e)

# 测试2: 时间序列监测
print('\n[2] 测试时间序列监测 (timeseries, 简化版5次扫描)')
payload2 = {
    'grid_size': 16,
    'edema_regions': [
        {'center_x': 8, 'center_y': 5, 'radius': 2}
    ],
    'num_scans': 5,
    'interval_seconds': 30,
    'expansion_rate': 0.08
}
try:
    resp = requests.post(f'{base}/api/simulation/timeseries', json=payload2, timeout=180)
    if resp.status_code == 200:
        d = resp.json()
        print('  任务ID:', d['task_id'])
        print('  扫描次数:', d['num_scans'], '次')
        print('  时间点:', [f'{t:.1f}min' for t in d['times_minutes']])
        print('  水肿平均σ序列:', [f'{v:.3f}' for v in d['time_series']['edema_avg_conductivity']])
        print('  水肿体积(像素):', d['time_series']['edema_volume_pixels'])
        print('  预测结果:')
        p = d['prediction']
        print(f'    σ斜率: {p["conductivity_slope_per_min"]:.6f}/min, R²={p["conductivity_r2"]:.4f}')
        print(f'    体积斜率: {p["volume_slope_per_min"]:.4f}像素/min, R²={p["volume_r2"]:.4f}')
        print(f'    30min预测σ={p["predicted_30min_conductivity"]:.4f}, 体积={p["predicted_30min_volume_pixels"]}像素')
        print(f'    严重程度: {p["severity_level"]}')
        print('  警告信息:')
        for w in d['warnings']:
            print(f'    - {w}')
        print('  ✓ 时间序列监测测试通过!')
    else:
        print('  失败:', resp.status_code, resp.text[:300])
except Exception as e:
    import traceback
    traceback.print_exc()
    print('  错误:', e)

print('\n' + '='*60)
print('全部测试完成!')
print('='*60)
