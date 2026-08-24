import onnx
from onnx import helper
from onnx import TensorProto
import os

def create_dummy_onnx():
    # Input tensor: shape (batch, 48000)
    input_tensor = helper.make_tensor_value_info('input', TensorProto.FLOAT, ['batch', 48000])
    # Output tensor: shape (batch, 2)
    output_tensor = helper.make_tensor_value_info('output', TensorProto.FLOAT, ['batch', 2])

    # Weights and bias for a simple linear layer
    # W shape: (48000, 2)
    # B shape: (2,)
    # Output = Input * W + B
    
    W = helper.make_tensor('W', TensorProto.FLOAT, [48000, 2], [0.0] * 48000 * 2)
    B = helper.make_tensor('B', TensorProto.FLOAT, [2], [0.0, 0.0])

    node = helper.make_node(
        'MatMul',
        inputs=['input', 'W'],
        outputs=['matmul_out'],
        name='matmul_node'
    )
    
    node2 = helper.make_node(
        'Add',
        inputs=['matmul_out', 'B'],
        outputs=['output'],
        name='add_node'
    )

    graph = helper.make_graph(
        [node, node2],
        'dummy_dhwani',
        [input_tensor],
        [output_tensor],
        initializer=[W, B]
    )

    opset = onnx.helper.make_opsetid('', 20)
    model = helper.make_model(graph, producer_name='dummy_maker', opset_imports=[opset])
    
    output_path = os.path.join(os.path.dirname(__file__), "dummy_dhwani.onnx")
    onnx.save(model, output_path)
    print(f"Created dummy ONNX model at {output_path}")

if __name__ == '__main__':
    create_dummy_onnx()
