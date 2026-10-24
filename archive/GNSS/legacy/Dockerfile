FROM ros:humble

# Set the working directory inside the container
WORKDIR /app

# Install dependencies

COPY ./requirements.txt .
RUN apt-get update && apt-get install -y python3-pip git && pip install -r requirements.txt 
RUN git clone https://github.com/tomojitakasu/RTKLIB && cd RTKLIB/app/str2str/gcc/ && \
make 

# Source ROS 2 environment
RUN echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc

# Copy the rest of the application files
COPY . .

# Command to run the script
CMD ["bash", "-c", "source /opt/ros/humble/setup.bash && \
./RTKLIB/app/str2str/gcc/str2str -in ntrip://$EMAIL_ADDR:none@rtk2go.com:2101/CanalTerris -out serial://${USB_NAME}:115200 && python3 src/GNSS.py"]
