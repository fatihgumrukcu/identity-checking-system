let cropper;
const fileInput = document.getElementById('fileInput');
const image = document.getElementById('image');
const cropperWrapper = document.getElementById('cropperWrapper');
const actionButtons = document.getElementById('actionButtons');
const uploadArea = document.getElementById('uploadArea');

// Drag and drop functionality
uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.style.borderColor = '#e17b47';
    uploadArea.style.background = '#fff7ed';
});

uploadArea.addEventListener('dragleave', (e) => {
    e.preventDefault();
    uploadArea.style.borderColor = '#e2e8f0';
    uploadArea.style.background = '#f8fafc';
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.style.borderColor = '#e2e8f0';
    uploadArea.style.background = '#f8fafc';
    
    const files = e.dataTransfer.files;
    if (files.length > 0 && files[0].type.startsWith('image/')) {
        fileInput.files = files;
        handleFileSelect(files[0]);
    }
});

fileInput.onchange = (e) => {
    const file = e.target.files[0];
    if (file) {
        handleFileSelect(file);
    }
};

function handleFileSelect(file) {
    const reader = new FileReader();
    reader.onload = (event) => {
        image.src = event.target.result;
        cropperWrapper.style.display = 'block';
        actionButtons.style.display = 'block';
        uploadArea.classList.add('has-file');
        uploadArea.querySelector('.file-label').textContent = `✅ ${file.name} selected`;
        
        if (cropper) cropper.destroy();
        
        cropper = new Cropper(image, {
            aspectRatio: 10 / 6,
            viewMode: 1,
            ready() {
                const face = document.querySelector('.cropper-face');
                const guide = document.createElement('div');
                guide.className = 'mrz-guide';
                guide.innerText = 'MRZ AREA';
                face.appendChild(guide);

                const overlay = document.createElement('div');
                overlay.className = 'scan-overlay';
                overlay.id = 'scanOverlay';
                overlay.innerHTML = '<div class="scan-line"></div>';
                face.appendChild(overlay);
            }
        });
    };
    reader.readAsDataURL(file);
}

document.getElementById('verifyBtn').onclick = () => {
    const overlay = document.getElementById('scanOverlay');
    const resultDiv = document.getElementById('result');
    
    overlay.style.display = 'block';
    resultDiv.innerHTML = `
        <div class="loading-message">
            <div class="spinner"></div>
            <span>⏳ Deep scanning in progress, analyzing data...</span>
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
            if(data.status === "ok") {
                resultDiv.className = 'success-card';
                resultDiv.innerHTML = `
                    <h3>✅ Analysis Successfully Completed</h3>
                    <pre>${JSON.stringify(data, null, 2)}</pre>
                `;
            } else {
                resultDiv.className = 'error-card';
                resultDiv.innerHTML = `<div>❌ Error: ${data.msg}</div>`;
            }
        }, remainingTime);
    })
    .catch(error => {
        overlay.style.display = 'none';
        resultDiv.className = 'error-card';
        resultDiv.innerHTML = `<div>❌ Connection error: ${error.message}</div>`;
    });
};
