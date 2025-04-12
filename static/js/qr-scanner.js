document.addEventListener('DOMContentLoaded', function() {
    const startCameraButton = document.getElementById('start-camera');
    const stopCameraButton = document.getElementById('stop-camera');
    const cameraPreview = document.getElementById('camera-preview');
    const cameraCanvas = document.getElementById('camera-canvas');
    const qrReaderResults = document.getElementById('qr-reader-results');
    const qrDataInput = document.getElementById('qr-data');
    const passForm = document.getElementById('pass-form');
    
    let stream = null;
    let scanning = false;
    let animationFrameId = null;
    
    function startCamera() {
        navigator.mediaDevices.getUserMedia({ 
            video: { 
                facingMode: "environment",
                width: { ideal: 1280 },
                height: { ideal: 720 } 
            } 
        })
        .then(function(mediaStream) {
            stream = mediaStream;
            cameraPreview.srcObject = stream;
            startCameraButton.style.display = 'none';
            stopCameraButton.style.display = 'inline-block';
            qrReaderResults.innerHTML = `
                <div class="alert info">
                    <p>Kamera aktivní, automaticky hledám QR kód...</p>
                </div>
            `;
            
            cameraCanvas.width = cameraPreview.videoWidth || 640;
            cameraCanvas.height = cameraPreview.videoHeight || 480;
            
            cameraPreview.onloadedmetadata = function() {
                startScanning();
            };
        })
        .catch(function(err) {
            qrReaderResults.innerHTML = `
                <div class="alert error">
                    <p>Chyba při přístupu ke kameře:</p>
                    <p>${err}</p>
                    <p>Ujistěte se, že jste udělili přístup ke kameře nebo zkuste jiný prohlížeč.</p>
                </div>
            `;
        });
    }
    
    function stopCamera() {
        if (stream) {
            stream.getTracks().forEach(track => {
                track.stop();
            });
            cameraPreview.srcObject = null;
            stream = null;
            
            startCameraButton.style.display = 'inline-block';
            stopCameraButton.style.display = 'none';
            
            if (animationFrameId) {
                cancelAnimationFrame(animationFrameId);
                animationFrameId = null;
            }
            scanning = false;
        }
    }
    
    function startScanning() {
        if (!stream) return;
        
        scanning = true;
        scanFrame();
    }
    
    function scanFrame() {
        if (!scanning) return;

        if (cameraPreview.readyState === cameraPreview.HAVE_ENOUGH_DATA) {
            const canvas = cameraCanvas;
            const ctx = canvas.getContext('2d');
            
            if (canvas.width !== cameraPreview.videoWidth || canvas.height !== cameraPreview.videoHeight) {
                canvas.width = cameraPreview.videoWidth;
                canvas.height = cameraPreview.videoHeight;
            }
            
            ctx.drawImage(cameraPreview, 0, 0, canvas.width, canvas.height);
            
            try {
                const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                const code = jsQR(imageData.data, imageData.width, imageData.height);
                
                if (code) {
                    scanning = false;
                    onScanSuccess(code.data);
                    return;
                }
            } catch (e) {
                console.error("Error during QR scanning:", e);
            }
        }
        
        animationFrameId = requestAnimationFrame(scanFrame);
    }
    
    function onScanSuccess(decodedText) {
        qrReaderResults.innerHTML = `
            <div class="alert success">
                <p>QR kód úspěšně naskenován!</p>
            </div>
        `;

        qrDataInput.value = decodedText;

        passForm.style.display = 'block';

        stopCamera();
    }
    
    startCameraButton.addEventListener('click', startCamera);
    stopCameraButton.addEventListener('click', stopCamera);
});
