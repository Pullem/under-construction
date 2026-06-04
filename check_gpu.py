import torch
import sys

def test_forensic_gpu():
	print("--- Video Forensic GPU-Check ---")
	
	# 1. Python & PyTorch Version
	print(f"Python Version: {sys.version}")
	print(f"PyTorch Version: {torch.__version__}")

	# 2. CUDA Check
	cuda_available = torch.cuda.is_available()
	print(f"CUDA verfügbar: {'✅ JA' if cuda_available else '❌ NEIN'}")

	if not cuda_available:
		print("\nFEHLER: CUDA wurde nicht gefunden.")
		print("Prüfe, ob das CUDA Toolkit im System-Pfad (PATH) liegt.")
		return

	# 3. GPU Details
	gpu_count = torch.cuda.device_count()
	current_device = torch.cuda.current_device()
	gpu_name = torch.cuda.get_device_name(current_device)
	
	print(f"Anzahl GPUs: {gpu_count}")
	print(f"Aktive GPU: {gpu_name}")

	# 4. cuDNN Check (Wichtig für AI-Enhancer)
	cudnn_enabled = torch.backends.cudnn.enabled
	cudnn_version = torch.backends.cudnn.version()
	print(f"cuDNN aktiv: {'✅ JA' if cudnn_enabled else '❌ NEIN'}")
	print(f"cuDNN Version: {cudnn_version}")

	# 5. Praxis-Test: Matrix-Multiplikation auf der RTX 2080
	print("\nFühre Test-Berechnung auf GPU aus...")
	try:
		# Erzeuge zwei große Zufallsmatrizen direkt auf der GPU
		x = torch.rand(5000, 5000).cuda()
		y = torch.rand(5000, 5000).cuda()
		
		# Berechnung (Matrix-Multiplikation)
		start_event = torch.cuda.Event(enable_timing=True)
		end_event = torch.cuda.Event(enable_timing=True)

		start_event.record()
		z = torch.matmul(x, y)
		end_event.record()

		torch.cuda.synchronize() # Warten bis Fertigstellung
		
		print(f"✅ Berechnung erfolgreich!")
		print(f"Dauer (5000x5000 Matrix): {start_event.elapsed_time(end_event):.2f} ms")
		
	except Exception as e:
		print(f"❌ Fehler bei der GPU-Berechnung: {e}")

if __name__ == "__main__":
	test_forensic_gpu()