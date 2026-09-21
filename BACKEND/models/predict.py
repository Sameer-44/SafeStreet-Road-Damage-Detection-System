import torch
import torch.nn as nn
import torchvision.transforms as transforms # preprocess  the image
from PIL import Image  # open , resize, convert 
import sys  # through this module takes the input from the terminal 
import os  # interacting with file system
import time #  track time 
import io   # input output operations 

# Enable performance optimizations
torch.set_num_threads(4)  # this threads used for the pytorch internal operations such as data loading,tensor operations etc
torch.backends.cudnn.benchmark = True  #this sets fastest algorithm for your convolution layers on fixed-size inputs 

# Define the CNN Model (Must match training architecture)
class CNN(nn.Module):  
    def __init__(self):
        super(CNN, self).__init__()
        self.conv1 = nn.Conv2d(3, 16, kernel_size=3, stride=1, padding=1) 
        self.conv2 = nn.Conv2d(16, 32, kernel_size=3, stride=1, padding=1) 
        self.conv3 = nn.Conv2d(32, 64, kernel_size=3, stride=1, padding=1) 
        self.pool = nn.MaxPool2d(2, 2) # reduces the dimension, speed up and prevents overfiting 
        self.fc1 = nn.Linear(64 * 16 * 16, 128)
        self.fc2 = nn.Linear(128, 1) 
        self.sigmoid = nn.Sigmoid()
        # Use ReLU modules directly for better performance
        self.relu = nn.ReLU(inplace=True)  # here relu introduces the non-linearty 

    def forward(self, x):
        x = self.pool(self.relu(self.conv1(x)))  # low-level features
        x = self.pool(self.relu(self.conv2(x)))  # middle-level features
        x = self.pool(self.relu(self.conv3(x)))  # high-level features 
        x = x.view(-1, 64 * 16 * 16) # converts 3D to 1D 
        x = self.relu(self.fc1(x))  # reduces to 128 
        x = self.fc2(x)  # reduces to 1 neuron
        x = self.sigmoid(x) # predict range b/w 0 and 1 
        return x

# Global variables for model and transform to avoid reloading
device = torch.device("cuda" if torch.cuda.is_available() else "cpu") # computer unified device architecture 
model = None
transform = None
 
def load_model():
    """Load model only once and cache it"""
    global model, transform, device
    
    if model is None:
        start_time = time.time() # how long the model takes time to load 
        
        # Load model
        model_path = os.path.join(os.path.dirname(__file__), "road.pth") # stores the model weights 
        model = CNN().to(device)
        
        
        if device.type == 'cpu':
            # Load state dict first
            model.load_state_dict(torch.load(model_path, map_location=device))
            model.eval()
            # Create example input for tracing
            example = torch.rand(1, 3, 128, 128).to(device) # we create a dummy input to trace the model 
            # JIT(just in time) trace the model
            model = torch.jit.trace(model, example) # for the faster execution we use this line 
        else:
            # For GPU, just load normally
            model.load_state_dict(torch.load(model_path, map_location=device))
            model.eval()
            
        # Use half precision if GPU is available for faster inference
        if device.type == 'cuda':
            model = model.half() # to calculate the fast we use this half precision and less memory usage 
            
        # Define optimized transform pipeline
        transform = transforms.Compose([
            transforms.Resize((128, 128), antialias=True),  # Use antialiasing for better quality
            transforms.ToTensor(),
            transforms.Normalize((0.5,), (0.5,))
        ])
        
        print(f"Model loaded in {time.time() - start_time:.2f} seconds on {device}") # runs time for the model execution
    
    return model, transform

# Optimized prediction function
def predict_image(image_path):
    """Predict if an image contains a road with optimized processing"""
    start_time = time.time() # how long the model takes to load 
    
    # Load model (calls previous loaded function)
    model, transform = load_model()
    
    # Efficient image loading
    try:
        
        with open(image_path, 'rb') as f:# reads the image in the binary memory 
            image_bytes = f.read()
            
        # Load image from memory into pil image
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB") # binary image to rgb 
        
        
        input_tensor = transform(image).unsqueeze(0) # shape[1,3,128,128]
        
        # Use half precision  on GPU
        if device.type == 'cuda':
            input_tensor = input_tensor.half() # for easy calculation and less memory storage
            
        input_tensor = input_tensor.to(device)
        
        # Run inference with optimizations
        with torch.no_grad():
            output = model(input_tensor)
        
        # Process result
        confidence = output.item()
        prediction = "Not a Road" if confidence < 0.5 else "Road"
        
        # Print timing and confidence information
        inference_time = time.time() - start_time
        print(f"{prediction} (confidence: {confidence:.4f}, time: {inference_time:.3f}s)")
        
        return prediction
        
    except Exception as e:  # retuns error if image not found etc
        print(f"Error during prediction: {e}") 
        return "Error"
# argv --> argument vector it provide the sys module, it contains everything which is in command line 
if __name__ == "__main__": 
    if len(sys.argv) < 2: 
        print("Usage: python predict.py <image_path>")
        sys.exit(1)

    image_path = sys.argv[1]
    if not os.path.exists(image_path): # checks the file exists in given path
        print(f"Error: Image file '{image_path}' not found!")
        sys.exit(1)

    # Time the entire prediction process
    overall_start = time.time()
    result = predict_image(image_path)
    print(f"{result} (total time: {time.time() - overall_start:.3f}s)")  # Send prediction output to Node.js server
