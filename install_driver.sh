sudo chmod 777 /opt/deeplearning/driver-version.sh
sudo echo "export DRIVER_VERSION=550.90.07" > /opt/deeplearning/driver-version.sh
sudo echo "export DRIVER_UBUNTU_DEB="nvidia-driver-local-repo-ubuntu1804-550.90.07_1.0-1_amd64.deb"" >> /opt/deeplearning/driver-version.sh
sudo echo "export DRIVER_UBUNTU_CUDA_VERSION="12.4"" >> /opt/deeplearning/driver-version.sh
sudo echo "export DRIVER_UBUNTU_PKG=nvidia-driver-550" >> /opt/deeplearning/driver-version.sh
sudo /opt/deeplearning/install-driver.sh
