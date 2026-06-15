import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import requests
import numpy as np
import base64

base = 'http://localhost:8001'

print('='*70)
print('阶段3 新功能API测试：电极优化 + DICOM导出')
print('='*70)

# 先跑一次标准2D仿真，获取真实/重建电导率矩阵供评估使用
print('\n[0] 预运行：标准2D仿真获取参考数据')
payload0 = {
    'grid_size': 16,
    'edema_regions': [
        {'center_x': 8, 'center_y': 6, 'radius': 2, 'conductivity_factor': 2.0}
    ],
    'drawn_mask': None
}
try:
    resp0 = requests.post(f'{base}/api/simulation/2d', json=payload0, timeout=120)
    if resp0.status_code == 200:
        d0 = resp0.json()
        true_mat = d0['true_conductivity']
        rec_mat = d0['reconstructed_conductivity']
        print(f'  已获取: true={len(true_mat)}x{len(true_mat[0])}, rec={len(rec_mat)}x{len(rec_mat[0])}')
    else:
        print('  失败:', resp0.status_code, resp0.text[:150])
        sys.exit(1)
except Exception as e:
    import traceback; traceback.print_exc()
    sys.exit(1)

# 测试1: 图像质量评估
print('\n[1] 图像质量评估 (evaluate_quality)')
try:
    resp = requests.post(
        f'{base}/api/simulation/evaluate_quality',
        json={'true_conductivity': true_mat, 'reconstructed_conductivity': rec_mat},
        timeout=30
    )
    if resp.status_code == 200:
        d = resp.json()
        m = d['metrics']
        print(f'  MSE = {m["mse"]:.6f}')
        print(f'  RMSE = {m["rmse"]:.6f}')
        print(f'  MAE = {m["mae"]:.6f}')
        print(f'  SSIM = {m["ssim"]:.4f}')
        print(f'  PSNR = {m["psnr"]:.2f} dB')
        print(f'  Correlation = {m["correlation"]:.4f}')
        print(f'  综合质量分数 = {d["overall_quality_score"]*100:.1f}%')
        print('  ✓ 图像质量评估测试通过!')
    else:
        print('  失败:', resp.status_code, resp.text[:200])
except Exception as e:
    import traceback; traceback.print_exc()

# 测试2: 电极优化 (不带当前质量)
print('\n[2] 电极布局优化 (electrode_optimization, 仅推荐)')
try:
    resp = requests.post(f'{base}/api/simulation/electrode_optimization', json={
        'grid_size': 16,
        'num_pairs_to_select': 8
    }, timeout=60)
    if resp.status_code == 200:
        d = resp.json()
        print(f'  任务ID: {d["task_id"]}')
        print(f'  选中电极对数: {d["num_selected_pairs"]}')
        print(f'  独立电极数: {d["num_unique_electrodes"]}')
        print(f'  适应度分数: {d["fitness_score"]:.4f}')
        print(f'  覆盖度: {d["coverage_score"]:.4f}, 角度分散: {d["spread_score"]:.4f}, 均衡: {d["balance_score"]:.4f}')
        print(f'  推荐电极对示例(前5): {d["selected_pairs"][:5]}')
        print(f'  迭代代数: {len(d["generation_best_history"])} 代')
        print(f'  最终适应度: {d["generation_best_history"][-1]:.4f} (起始: {d["generation_best_history"][0]:.4f})')
        print('  ✓ 电极优化(推荐)测试通过!')
    else:
        print('  失败:', resp.status_code, resp.text[:200])
except Exception as e:
    import traceback; traceback.print_exc()

# 测试3: 电极优化 (带当前重建质量)
print('\n[3] 电极布局优化 (electrode_optimization, 带当前质量)')
try:
    resp = requests.post(f'{base}/api/simulation/electrode_optimization', json={
        'grid_size': 16,
        'num_pairs_to_select': 8,
        'true_conductivity': true_mat,
        'reconstructed_conductivity': rec_mat
    }, timeout=60)
    if resp.status_code == 200:
        d = resp.json()
        print(f'  推荐文本: {d["recommendation"][:80]}...')
        if 'current_quality' in d:
            cq = d['current_quality']
            print(f'  当前综合质量: {cq["overall_quality_score"]*100:.1f}%')
        print(f'  改进潜力: {d.get("improvement_potential", 0):.4f}')
        print('  ✓ 电极优化(带质量)测试通过!')
    else:
        print('  失败:', resp.status_code, resp.text[:200])
except Exception as e:
    import traceback; traceback.print_exc()

# 测试4: DICOM导出 (重建图)
print('\n[4] DICOM导出 (单重建图)')
try:
    sim_result = {
        'task_id': 'TEST-' + str(np.random.randint(100000, 999999)),
        'reconstructed_conductivity': rec_mat,
        'true_conductivity': true_mat
    }
    resp = requests.post(f'{base}/api/simulation/export_dicom', json={
        'simulation_result': sim_result,
        'export_type': 'reconstructed'
    }, timeout=60)
    if resp.status_code == 200:
        d = resp.json()
        print(f'  状态: {d["status"]}, 文件数: {d["num_files"]}')
        f = d['files'][0]
        print(f'  文件名: {f["filename"]}')
        print(f'  矩阵形状: {f["matrix_shape"]}')
        print(f'  σ 范围: [{f["matrix_min"]:.4f}, {f["matrix_max"]:.4f}] (均值 {f["matrix_mean"]:.4f})')
        print(f'  DICOM Base64长度: {len(f["dicom_bytes_base64"])} chars')
        dicom_bytes = base64.b64decode(f['dicom_bytes_base64'])
        print(f'  解码后DICOM大小: {len(dicom_bytes)} bytes')
        print(f'  DICOM头部 magic: {dicom_bytes[128:132]} (应=b"DICM")')
        assert dicom_bytes[128:132] == b'DICM', 'DICM magic校验失败!'
        print('  ✓ DICOM格式校验通过!')
        # 保存到文件验证
        with open('d:/AA_code/032/test_output.dcm', 'wb') as fp:
            fp.write(dicom_bytes)
        print('  ✓ 已保存样例到 test_output.dcm')
        print('  ✓ DICOM导出测试通过!')
    else:
        print('  失败:', resp.status_code, resp.text[:200])
except Exception as e:
    import traceback; traceback.print_exc()

# 测试5: DICOM导出 (多频)
print('\n[5] DICOM导出 (多频全量)')
try:
    # 先跑多频仿真
    mf_resp = requests.post(f'{base}/api/simulation/multifrequency', json={
        'grid_size': 16, 'edema_regions': payload0['edema_regions'], 'drawn_mask': None
    }, timeout=120)
    if mf_resp.status_code != 200:
        print('  多频仿真失败，跳过')
    else:
        mf = mf_resp.json()
        sim_result = {
            'task_id': 'MF-TEST-' + str(np.random.randint(100000, 999999)),
            'reconstructed_conductivity': mf['fused_reconstruction'],
            'fused_reconstruction': mf['fused_reconstruction'],
            'reconstructions': mf['reconstructions'],
            'cole_cole_params': mf['cole_cole_params']
        }
        resp = requests.post(f'{base}/api/simulation/export_dicom', json={
            'simulation_result': sim_result,
            'export_type': 'multifreq_all'
        }, timeout=120)
        if resp.status_code == 200:
            d = resp.json()
            print(f'  导出文件数: {d["num_files"]}')
            for f in d['files']:
                print(f'    - {f["filename"]}: {len(f["dicom_bytes_base64"])} chars, shape={f["matrix_shape"]}')
            print('  ✓ 多频DICOM批量导出测试通过!')
        else:
            print('  失败:', resp.status_code, resp.text[:200])
except Exception as e:
    import traceback; traceback.print_exc()

print('\n' + '='*70)
print('阶段3全部功能测试完成!')
print('='*70)
