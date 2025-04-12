document.addEventListener('DOMContentLoaded', function() {
    const startCameraButton = document.getElementById('start-camera');
    const stopCameraButton = document.getElementById('stop-camera');
    const cameraPreview = document.getElementById('camera-preview');
    const cameraCanvas = document.getElementById('camera-canvas');
    const qrReaderResults = document.getElementById('qr-reader-results');
    const qrResultCard = document.getElementById('qr-result');
    const downloadQrButton = document.getElementById('download-qr');
    const qrCanvas = document.getElementById('qr-canvas');
    
    let stream = null;
    let lastScannedQrCode = null;
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
            
            // Setup canvas for scanning
            cameraCanvas.width = cameraPreview.videoWidth || 640;
            cameraCanvas.height = cameraPreview.videoHeight || 480;
            
            // Wait for video to be ready
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

        // Make sure video is playing and ready
        if (cameraPreview.readyState === cameraPreview.HAVE_ENOUGH_DATA) {
            const canvas = cameraCanvas;
            const ctx = canvas.getContext('2d');
            
            // Make sure canvas dimensions match the current video dimensions
            if (canvas.width !== cameraPreview.videoWidth || canvas.height !== cameraPreview.videoHeight) {
                canvas.width = cameraPreview.videoWidth;
                canvas.height = cameraPreview.videoHeight;
            }
            
            // Draw current video frame to canvas
            ctx.drawImage(cameraPreview, 0, 0, canvas.width, canvas.height);
            
            // Get image data for                    to process
            try {
                const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
                const code = jsQR(imageData.data, imageData.width, imageData.height);
                
                if (code) {
                    // QR code found
                    scanning = false;
                    onScanSuccess(code.data);
                    return;
                }
            } catch (e) {
                console.error("Error during QR scanning:", e);
            }
        }
        
        // Continue scanning
        animationFrameId = requestAnimationFrame(scanFrame);
    }
    
    function generateQRCode(data) {
        const ctx = qrCanvas.getContext('2d');
        const size = 300;
        
        qrCanvas.width = size;
        qrCanvas.height = size;
        
        ctx.fillStyle = 'white';
        ctx.fillRect(0, 0, size, size);
        
        const script = document.createElement('script');
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/qrious/4.0.2/qrious.min.js';
        script.onload = function() {
            new QRious({
                element: qrCanvas,
                value: data,
                size: size,
                level: 'M',
                background: 'white',
                foreground: 'black',
                padding: 10
            });
        };
        document.head.appendChild(script);
    }
    
    function onScanSuccess(decodedText) {
        qrReaderResults.innerHTML = `
            <div class="alert success">
                <p>QR kód úspěšně naskenován!</p>
            </div>
        `;
        
        lastScannedQrCode = decodedText;
        
        // Play success sound if available
        const audio = new Audio('/static/sounds/beep.mp3');
        audio.play().catch(e => console.log('Audio play failed:', e));
        
        generateQRCode(decodedText);
        qrResultCard.style.display = 'block';
        
        stopCamera();
    }
    
    function downloadQR() {
        if (!qrCanvas) return;
        
        const link = document.createElement('a');
        link.download = 'OnkoPass.png';
        link.href = qrCanvas.toDataURL('image/png');
        link.click();
    }
    
    startCameraButton.addEventListener('click', startCamera);
    stopCameraButton.addEventListener('click', stopCamera);
    downloadQrButton.addEventListener('click', downloadQR);
});
