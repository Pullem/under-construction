#include <cuda_runtime.h>
#include <stdio.h>

__global__ void testKernel(int *value)
{
    *value = 123;
}

int main()
{
    int *deviceValue = nullptr;
    int hostValue = 0;

    cudaError_t err = cudaMalloc(&deviceValue, sizeof(int));
    if (err != cudaSuccess) {
        printf("cudaMalloc: %s\n", cudaGetErrorString(err));
        return 1;
    }

    testKernel<<<1, 1>>>(deviceValue);

    err = cudaDeviceSynchronize();
    if (err == cudaSuccess)
        err = cudaMemcpy(&hostValue, deviceValue, sizeof(int),
                         cudaMemcpyDeviceToHost);

    cudaFree(deviceValue);

    if (err != cudaSuccess) {
        printf("CUDA-Fehler: %s\n", cudaGetErrorString(err));
        return 2;
    }

    printf("CUDA-Test erfolgreich: %d\n", hostValue);
    return hostValue == 123 ? 0 : 3;
}