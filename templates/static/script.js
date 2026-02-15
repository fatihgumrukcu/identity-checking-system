document.addEventListener('DOMContentLoaded', () => {
    let cropper;
    const fileInput = document.getElementById('fileInput');
    const image = document.getElementById('image');
    const cropperWrapper = document.getElementById('cropperWrapper');
    const actionButtons = document.getElementById('actionButtons');
    const uploadArea = document.getElementById('uploadArea');
    const resultDiv = document.getElementById('result');

    // Drag and drop functionality
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.style.borderColor = '#3b82f6';
        uploadArea.style.background = 'rgba(59, 130, 246, 0.05)';
    });

    uploadArea.addEventListener('dragleave', (e) => {
        e.preventDefault();
        uploadArea.style.borderColor = 'rgba(255, 255, 255, 0.2)';
        uploadArea.style.background = 'rgba(255, 255, 255, 0.02)';
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.style.borderColor = 'rgba(255, 255, 255, 0.2)';
        uploadArea.style.background = 'rgba(255, 255, 255, 0.02)';
        
        const files = e.dataTransfer.files;
        if (files.length > 0 && files[0].type.startsWith('image/')) {
            fileInput.files = files;
            handleFileSelect(files[0]);
        }
    });

    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            handleFileSelect(file);
        }
    });

    function handleFileSelect(file) {
        const reader = new FileReader();
        reader.onload = (event) => {
            image.src = event.target.result;
            cropperWrapper.style.display = 'block';
            actionButtons.style.display = 'block';
            uploadArea.classList.add('has-file');
            
            if (cropper) cropper.destroy();
            
            cropper = new Cropper(image, {
                aspectRatio: 10 / 6,
                viewMode: 1,
                autoCropArea: 0.8,
                responsive: true,
                restore: true,
                guides: true,
                center: true,
                highlight: true,
                cropBoxMovable: true,
                cropBoxResizable: true,
                toggleDragModeOnDblclick: true,
                ready() {
                    const guide = document.createElement('div');
                    guide.className = 'mrz-guide';
                    guide.innerText = 'MRZ ALANI';
                    document.querySelector('.cropper-face')?.appendChild(guide);

                    const overlay = document.createElement('div');
                    overlay.className = 'scan-overlay';
                    overlay.id = 'scanOverlay';
                    overlay.innerHTML = '<div class="scan-line"></div>';
                    document.querySelector('.cropper-face')?.appendChild(overlay);
                }
            });
        };
        reader.readAsDataURL(file);
    }

    document.getElementById('verifyBtn').addEventListener('click', () => {
        const overlay = document.getElementById('scanOverlay');
        
        overlay.style.display = 'block';
        resultDiv.innerHTML = `
            <div class="loading-message">
                <div class="spinner"></div>
                <span>AI doğrulama işlemi devam ediyor...</span>
            </div>
        `;

        const canvas = cropper.getCroppedCanvas({ width: 1000, height: 600 });
        const dataUrl = canvas.toDataURL('image/jpeg');

        const startTime = Date.now();

        fetch('/upload', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ image: dataUrl })
        })
        .then(res => res.json())
        .then(data => {
            const elapsedTime = Date.now() - startTime;
            const minWait = 3000;
            const remainingTime = Math.max(0, minWait - elapsedTime);

            setTimeout(() => {
                overlay.style.display = 'none';
                if (data.status === "success") {
                    resultDiv.className = 'success-card';
                    resultDiv.innerHTML = `
                        <h3>✓ Doğrulama Başarılı</h3>
                        <pre>${JSON.stringify(data, null, 2)}</pre>
                    `;
                } else {
                    resultDiv.className = 'error-card';
                    resultDiv.innerHTML = `<div>✗ Hata: ${data.message || 'Bilinmeyen hata'}</div>`;
                }
            }, remainingTime);
        })
        .catch(error => {
            overlay.style.display = 'none';
            resultDiv.className = 'error-card';
            resultDiv.innerHTML = `<div>✗ Bağlantı hatası: ${error.message}</div>`;
        });
    });
});