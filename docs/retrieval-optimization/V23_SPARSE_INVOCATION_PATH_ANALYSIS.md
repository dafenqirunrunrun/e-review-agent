# V2.3 Sparse Invocation Path Analysis

```json
{
  "comparisons": {
    "PathA_vs_PathB": [
      {
        "expectedEffect": "none",
        "field": "batchSizes",
        "materialDifference": false,
        "pathAValueHash": "d51c1a6f9bfc1cad62b64cf35c36647e4796570a3c3e59961e631019f68c15bb",
        "pathBValueHash": "d51c1a6f9bfc1cad62b64cf35c36647e4796570a3c3e59961e631019f68c15bb"
      },
      {
        "expectedEffect": "none",
        "field": "device",
        "materialDifference": false,
        "pathAValueHash": "0e792c2f57836f3d30846b3702a42c59764933821815a4d304d951d24a6d7a65",
        "pathBValueHash": "0e792c2f57836f3d30846b3702a42c59764933821815a4d304d951d24a6d7a65"
      },
      {
        "expectedEffect": "none",
        "field": "encodeArgumentsHash",
        "materialDifference": false,
        "pathAValueHash": "60863232f7b240706bcd4ef940b81e5601a0160c1bf9c1591e1f946dbe4dccd3",
        "pathBValueHash": "60863232f7b240706bcd4ef940b81e5601a0160c1bf9c1591e1f946dbe4dccd3"
      },
      {
        "expectedEffect": "may change output extraction and post-processing path",
        "field": "encodeMethod",
        "materialDifference": true,
        "pathAValueHash": "ce91d807eb29055283b8c2869c154110f4f07172f069c4d97fc5f62620f9ca78",
        "pathBValueHash": "2b8087ee3269bac4aafff7acaddb200dd1ff50cec1ad71634576383f007f7b78"
      },
      {
        "expectedEffect": "none",
        "field": "instruction",
        "materialDifference": false,
        "pathAValueHash": "74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b",
        "pathBValueHash": "74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b"
      },
      {
        "expectedEffect": "none",
        "field": "maxLength",
        "materialDifference": false,
        "pathAValueHash": "2747b7c718564ba5f066f0523b03e17f6a496b06851333d2d59ab6d863225848",
        "pathBValueHash": "2747b7c718564ba5f066f0523b03e17f6a496b06851333d2d59ab6d863225848"
      },
      {
        "expectedEffect": "none",
        "field": "minimumSparseWeight",
        "materialDifference": false,
        "pathAValueHash": "8aed642bf5118b9d3c859bd4be35ecac75b6e873cce34e7b6f554b06f75550d7",
        "pathBValueHash": "8aed642bf5118b9d3c859bd4be35ecac75b6e873cce34e7b6f554b06f75550d7"
      },
      {
        "expectedEffect": "none",
        "field": "modelClass",
        "materialDifference": false,
        "pathAValueHash": "dac484fd0f6374631c377fd7f505af9e64df704d18eb97492b654f9819e5db7e",
        "pathBValueHash": "dac484fd0f6374631c377fd7f505af9e64df704d18eb97492b654f9819e5db7e"
      },
      {
        "expectedEffect": "none",
        "field": "modelConstructorArgumentsHash",
        "materialDifference": false,
        "pathAValueHash": "98cd018aa5c16b01189badfef8aa4b91bc07aeea7bfd94eb4daad55db1a5272a",
        "pathBValueHash": "98cd018aa5c16b01189badfef8aa4b91bc07aeea7bfd94eb4daad55db1a5272a"
      },
      {
        "expectedEffect": "none",
        "field": "normalizeEmbeddings",
        "materialDifference": false,
        "pathAValueHash": "fcbcf165908dd18a9e49f7ff27810176db8e9f63b4352213741664245224f8aa",
        "pathBValueHash": "fcbcf165908dd18a9e49f7ff27810176db8e9f63b4352213741664245224f8aa"
      },
      {
        "expectedEffect": "none",
        "field": "outputFieldName",
        "materialDifference": false,
        "pathAValueHash": "3e6d0e5fe7f1fdc7ee2d8b94e3810ea0f4c1c2b03d8a98b7ed48da5ce1fd36d8",
        "pathBValueHash": "3e6d0e5fe7f1fdc7ee2d8b94e3810ea0f4c1c2b03d8a98b7ed48da5ce1fd36d8"
      },
      {
        "expectedEffect": "may change raw token key representation",
        "field": "outputSchemaVersion",
        "materialDifference": true,
        "pathAValueHash": "75ce909f320ee06f51009d4c99fd413afff1ce1f0287a71ec91f7a66f7e766e4",
        "pathBValueHash": "51e867d782816d94aec6fa612bca862ccf1d2ea3fc137eb214418c4bf5b950f2"
      },
      {
        "expectedEffect": "may change token id conversion and filtering",
        "field": "postProcessorVersion",
        "materialDifference": true,
        "pathAValueHash": "956f826535f4299f837a8aecf3a621723c9877f213fee16e7ed5c83dc8526b28",
        "pathBValueHash": "30a0924a3360be687d1df9fcbbfdff62c01bc0fd14036ab9076cf7f451568666"
      },
      {
        "expectedEffect": "none",
        "field": "queryInstruction",
        "materialDifference": false,
        "pathAValueHash": "74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b",
        "pathBValueHash": "74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b"
      },
      {
        "expectedEffect": "none",
        "field": "returnColbertVecs",
        "materialDifference": false,
        "pathAValueHash": "fcbcf165908dd18a9e49f7ff27810176db8e9f63b4352213741664245224f8aa",
        "pathBValueHash": "fcbcf165908dd18a9e49f7ff27810176db8e9f63b4352213741664245224f8aa"
      },
      {
        "expectedEffect": "none",
        "field": "returnDense",
        "materialDifference": false,
        "pathAValueHash": "fcbcf165908dd18a9e49f7ff27810176db8e9f63b4352213741664245224f8aa",
        "pathBValueHash": "fcbcf165908dd18a9e49f7ff27810176db8e9f63b4352213741664245224f8aa"
      },
      {
        "expectedEffect": "none",
        "field": "returnSparse",
        "materialDifference": false,
        "pathAValueHash": "b5bea41b6c623f7c09f1bf24dcae58ebab3c0cdd90ad966bc43a45b44867e12b",
        "pathBValueHash": "b5bea41b6c623f7c09f1bf24dcae58ebab3c0cdd90ad966bc43a45b44867e12b"
      },
      {
        "expectedEffect": "none",
        "field": "specialTokenFilterHash",
        "materialDifference": false,
        "pathAValueHash": "70087bb2012d3515e9d26c697db63acfc0d34384175c17bba6fa7adff1228553",
        "pathBValueHash": "70087bb2012d3515e9d26c697db63acfc0d34384175c17bba6fa7adff1228553"
      },
      {
        "expectedEffect": "none",
        "field": "useFp16",
        "materialDifference": false,
        "pathAValueHash": "b5bea41b6c623f7c09f1bf24dcae58ebab3c0cdd90ad966bc43a45b44867e12b",
        "pathBValueHash": "b5bea41b6c623f7c09f1bf24dcae58ebab3c0cdd90ad966bc43a45b44867e12b"
      }
    ],
    "PathA_vs_PathC": [
      {
        "expectedEffect": "none",
        "field": "batchSizes",
        "materialDifference": false,
        "pathAValueHash": "d51c1a6f9bfc1cad62b64cf35c36647e4796570a3c3e59961e631019f68c15bb",
        "pathBValueHash": "d51c1a6f9bfc1cad62b64cf35c36647e4796570a3c3e59961e631019f68c15bb"
      },
      {
        "expectedEffect": "none",
        "field": "device",
        "materialDifference": false,
        "pathAValueHash": "0e792c2f57836f3d30846b3702a42c59764933821815a4d304d951d24a6d7a65",
        "pathBValueHash": "0e792c2f57836f3d30846b3702a42c59764933821815a4d304d951d24a6d7a65"
      },
      {
        "expectedEffect": "none",
        "field": "encodeArgumentsHash",
        "materialDifference": false,
        "pathAValueHash": "60863232f7b240706bcd4ef940b81e5601a0160c1bf9c1591e1f946dbe4dccd3",
        "pathBValueHash": "60863232f7b240706bcd4ef940b81e5601a0160c1bf9c1591e1f946dbe4dccd3"
      },
      {
        "expectedEffect": "may change output extraction and post-processing path",
        "field": "encodeMethod",
        "materialDifference": true,
        "pathAValueHash": "ce91d807eb29055283b8c2869c154110f4f07172f069c4d97fc5f62620f9ca78",
        "pathBValueHash": "2b8087ee3269bac4aafff7acaddb200dd1ff50cec1ad71634576383f007f7b78"
      },
      {
        "expectedEffect": "none",
        "field": "instruction",
        "materialDifference": false,
        "pathAValueHash": "74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b",
        "pathBValueHash": "74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b"
      },
      {
        "expectedEffect": "none",
        "field": "maxLength",
        "materialDifference": false,
        "pathAValueHash": "2747b7c718564ba5f066f0523b03e17f6a496b06851333d2d59ab6d863225848",
        "pathBValueHash": "2747b7c718564ba5f066f0523b03e17f6a496b06851333d2d59ab6d863225848"
      },
      {
        "expectedEffect": "none",
        "field": "minimumSparseWeight",
        "materialDifference": false,
        "pathAValueHash": "8aed642bf5118b9d3c859bd4be35ecac75b6e873cce34e7b6f554b06f75550d7",
        "pathBValueHash": "8aed642bf5118b9d3c859bd4be35ecac75b6e873cce34e7b6f554b06f75550d7"
      },
      {
        "expectedEffect": "none",
        "field": "modelClass",
        "materialDifference": false,
        "pathAValueHash": "dac484fd0f6374631c377fd7f505af9e64df704d18eb97492b654f9819e5db7e",
        "pathBValueHash": "dac484fd0f6374631c377fd7f505af9e64df704d18eb97492b654f9819e5db7e"
      },
      {
        "expectedEffect": "none",
        "field": "modelConstructorArgumentsHash",
        "materialDifference": false,
        "pathAValueHash": "98cd018aa5c16b01189badfef8aa4b91bc07aeea7bfd94eb4daad55db1a5272a",
        "pathBValueHash": "98cd018aa5c16b01189badfef8aa4b91bc07aeea7bfd94eb4daad55db1a5272a"
      },
      {
        "expectedEffect": "none",
        "field": "normalizeEmbeddings",
        "materialDifference": false,
        "pathAValueHash": "fcbcf165908dd18a9e49f7ff27810176db8e9f63b4352213741664245224f8aa",
        "pathBValueHash": "fcbcf165908dd18a9e49f7ff27810176db8e9f63b4352213741664245224f8aa"
      },
      {
        "expectedEffect": "none",
        "field": "outputFieldName",
        "materialDifference": false,
        "pathAValueHash": "3e6d0e5fe7f1fdc7ee2d8b94e3810ea0f4c1c2b03d8a98b7ed48da5ce1fd36d8",
        "pathBValueHash": "3e6d0e5fe7f1fdc7ee2d8b94e3810ea0f4c1c2b03d8a98b7ed48da5ce1fd36d8"
      },
      {
        "expectedEffect": "may change raw token key representation",
        "field": "outputSchemaVersion",
        "materialDifference": true,
        "pathAValueHash": "75ce909f320ee06f51009d4c99fd413afff1ce1f0287a71ec91f7a66f7e766e4",
        "pathBValueHash": "51e867d782816d94aec6fa612bca862ccf1d2ea3fc137eb214418c4bf5b950f2"
      },
      {
        "expectedEffect": "may change token id conversion and filtering",
        "field": "postProcessorVersion",
        "materialDifference": true,
        "pathAValueHash": "956f826535f4299f837a8aecf3a621723c9877f213fee16e7ed5c83dc8526b28",
        "pathBValueHash": "30a0924a3360be687d1df9fcbbfdff62c01bc0fd14036ab9076cf7f451568666"
      },
      {
        "expectedEffect": "none",
        "field": "queryInstruction",
        "materialDifference": false,
        "pathAValueHash": "74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b",
        "pathBValueHash": "74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b"
      },
      {
        "expectedEffect": "none",
        "field": "returnColbertVecs",
        "materialDifference": false,
        "pathAValueHash": "fcbcf165908dd18a9e49f7ff27810176db8e9f63b4352213741664245224f8aa",
        "pathBValueHash": "fcbcf165908dd18a9e49f7ff27810176db8e9f63b4352213741664245224f8aa"
      },
      {
        "expectedEffect": "none",
        "field": "returnDense",
        "materialDifference": false,
        "pathAValueHash": "fcbcf165908dd18a9e49f7ff27810176db8e9f63b4352213741664245224f8aa",
        "pathBValueHash": "fcbcf165908dd18a9e49f7ff27810176db8e9f63b4352213741664245224f8aa"
      },
      {
        "expectedEffect": "none",
        "field": "returnSparse",
        "materialDifference": false,
        "pathAValueHash": "b5bea41b6c623f7c09f1bf24dcae58ebab3c0cdd90ad966bc43a45b44867e12b",
        "pathBValueHash": "b5bea41b6c623f7c09f1bf24dcae58ebab3c0cdd90ad966bc43a45b44867e12b"
      },
      {
        "expectedEffect": "none",
        "field": "specialTokenFilterHash",
        "materialDifference": false,
        "pathAValueHash": "70087bb2012d3515e9d26c697db63acfc0d34384175c17bba6fa7adff1228553",
        "pathBValueHash": "70087bb2012d3515e9d26c697db63acfc0d34384175c17bba6fa7adff1228553"
      },
      {
        "expectedEffect": "none",
        "field": "useFp16",
        "materialDifference": false,
        "pathAValueHash": "b5bea41b6c623f7c09f1bf24dcae58ebab3c0cdd90ad966bc43a45b44867e12b",
        "pathBValueHash": "b5bea41b6c623f7c09f1bf24dcae58ebab3c0cdd90ad966bc43a45b44867e12b"
      }
    ],
    "PathB_vs_PathC": [
      {
        "expectedEffect": "none",
        "field": "batchSizes",
        "materialDifference": false,
        "pathAValueHash": "d51c1a6f9bfc1cad62b64cf35c36647e4796570a3c3e59961e631019f68c15bb",
        "pathBValueHash": "d51c1a6f9bfc1cad62b64cf35c36647e4796570a3c3e59961e631019f68c15bb"
      },
      {
        "expectedEffect": "none",
        "field": "device",
        "materialDifference": false,
        "pathAValueHash": "0e792c2f57836f3d30846b3702a42c59764933821815a4d304d951d24a6d7a65",
        "pathBValueHash": "0e792c2f57836f3d30846b3702a42c59764933821815a4d304d951d24a6d7a65"
      },
      {
        "expectedEffect": "none",
        "field": "encodeArgumentsHash",
        "materialDifference": false,
        "pathAValueHash": "60863232f7b240706bcd4ef940b81e5601a0160c1bf9c1591e1f946dbe4dccd3",
        "pathBValueHash": "60863232f7b240706bcd4ef940b81e5601a0160c1bf9c1591e1f946dbe4dccd3"
      },
      {
        "expectedEffect": "none",
        "field": "encodeMethod",
        "materialDifference": false,
        "pathAValueHash": "2b8087ee3269bac4aafff7acaddb200dd1ff50cec1ad71634576383f007f7b78",
        "pathBValueHash": "2b8087ee3269bac4aafff7acaddb200dd1ff50cec1ad71634576383f007f7b78"
      },
      {
        "expectedEffect": "none",
        "field": "instruction",
        "materialDifference": false,
        "pathAValueHash": "74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b",
        "pathBValueHash": "74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b"
      },
      {
        "expectedEffect": "none",
        "field": "maxLength",
        "materialDifference": false,
        "pathAValueHash": "2747b7c718564ba5f066f0523b03e17f6a496b06851333d2d59ab6d863225848",
        "pathBValueHash": "2747b7c718564ba5f066f0523b03e17f6a496b06851333d2d59ab6d863225848"
      },
      {
        "expectedEffect": "none",
        "field": "minimumSparseWeight",
        "materialDifference": false,
        "pathAValueHash": "8aed642bf5118b9d3c859bd4be35ecac75b6e873cce34e7b6f554b06f75550d7",
        "pathBValueHash": "8aed642bf5118b9d3c859bd4be35ecac75b6e873cce34e7b6f554b06f75550d7"
      },
      {
        "expectedEffect": "none",
        "field": "modelClass",
        "materialDifference": false,
        "pathAValueHash": "dac484fd0f6374631c377fd7f505af9e64df704d18eb97492b654f9819e5db7e",
        "pathBValueHash": "dac484fd0f6374631c377fd7f505af9e64df704d18eb97492b654f9819e5db7e"
      },
      {
        "expectedEffect": "none",
        "field": "modelConstructorArgumentsHash",
        "materialDifference": false,
        "pathAValueHash": "98cd018aa5c16b01189badfef8aa4b91bc07aeea7bfd94eb4daad55db1a5272a",
        "pathBValueHash": "98cd018aa5c16b01189badfef8aa4b91bc07aeea7bfd94eb4daad55db1a5272a"
      },
      {
        "expectedEffect": "none",
        "field": "normalizeEmbeddings",
        "materialDifference": false,
        "pathAValueHash": "fcbcf165908dd18a9e49f7ff27810176db8e9f63b4352213741664245224f8aa",
        "pathBValueHash": "fcbcf165908dd18a9e49f7ff27810176db8e9f63b4352213741664245224f8aa"
      },
      {
        "expectedEffect": "none",
        "field": "outputFieldName",
        "materialDifference": false,
        "pathAValueHash": "3e6d0e5fe7f1fdc7ee2d8b94e3810ea0f4c1c2b03d8a98b7ed48da5ce1fd36d8",
        "pathBValueHash": "3e6d0e5fe7f1fdc7ee2d8b94e3810ea0f4c1c2b03d8a98b7ed48da5ce1fd36d8"
      },
      {
        "expectedEffect": "none",
        "field": "outputSchemaVersion",
        "materialDifference": false,
        "pathAValueHash": "51e867d782816d94aec6fa612bca862ccf1d2ea3fc137eb214418c4bf5b950f2",
        "pathBValueHash": "51e867d782816d94aec6fa612bca862ccf1d2ea3fc137eb214418c4bf5b950f2"
      },
      {
        "expectedEffect": "none",
        "field": "postProcessorVersion",
        "materialDifference": false,
        "pathAValueHash": "30a0924a3360be687d1df9fcbbfdff62c01bc0fd14036ab9076cf7f451568666",
        "pathBValueHash": "30a0924a3360be687d1df9fcbbfdff62c01bc0fd14036ab9076cf7f451568666"
      },
      {
        "expectedEffect": "none",
        "field": "queryInstruction",
        "materialDifference": false,
        "pathAValueHash": "74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b",
        "pathBValueHash": "74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b"
      },
      {
        "expectedEffect": "none",
        "field": "returnColbertVecs",
        "materialDifference": false,
        "pathAValueHash": "fcbcf165908dd18a9e49f7ff27810176db8e9f63b4352213741664245224f8aa",
        "pathBValueHash": "fcbcf165908dd18a9e49f7ff27810176db8e9f63b4352213741664245224f8aa"
      },
      {
        "expectedEffect": "none",
        "field": "returnDense",
        "materialDifference": false,
        "pathAValueHash": "fcbcf165908dd18a9e49f7ff27810176db8e9f63b4352213741664245224f8aa",
        "pathBValueHash": "fcbcf165908dd18a9e49f7ff27810176db8e9f63b4352213741664245224f8aa"
      },
      {
        "expectedEffect": "none",
        "field": "returnSparse",
        "materialDifference": false,
        "pathAValueHash": "b5bea41b6c623f7c09f1bf24dcae58ebab3c0cdd90ad966bc43a45b44867e12b",
        "pathBValueHash": "b5bea41b6c623f7c09f1bf24dcae58ebab3c0cdd90ad966bc43a45b44867e12b"
      },
      {
        "expectedEffect": "none",
        "field": "specialTokenFilterHash",
        "materialDifference": false,
        "pathAValueHash": "70087bb2012d3515e9d26c697db63acfc0d34384175c17bba6fa7adff1228553",
        "pathBValueHash": "70087bb2012d3515e9d26c697db63acfc0d34384175c17bba6fa7adff1228553"
      },
      {
        "expectedEffect": "none",
        "field": "useFp16",
        "materialDifference": false,
        "pathAValueHash": "b5bea41b6c623f7c09f1bf24dcae58ebab3c0cdd90ad966bc43a45b44867e12b",
        "pathBValueHash": "b5bea41b6c623f7c09f1bf24dcae58ebab3c0cdd90ad966bc43a45b44867e12b"
      }
    ]
  },
  "conclusion": "INVOCATION_PARAMETER_DIVERGENCE_CONFIRMED",
  "gate": {
    "materialDifferenceFound": true,
    "status": "PASS"
  },
  "paths": {
    "DQA_CONTROL_PATH": {
      "batchSizes": [
        1,
        8
      ],
      "device": "cuda",
      "encodeArgumentsHash": "9d601027639776a3bad38a75dff80cbfd03b931c21a661049d0b31f17a18b0bd",
      "encodeMethod": "FlagEmbedding.encode",
      "instruction": null,
      "maxLength": 128,
      "minimumSparseWeight": 0.0,
      "modelClass": "FlagEmbedding.BGEM3FlagModel",
      "modelConstructorArgumentsHash": "27de6ae3da1136fd7c82eb429a873cbb5dcdee5634865fbb2744d7b1267706c3",
      "normalizeEmbeddings": false,
      "outputFieldName": "lexical_weights",
      "outputSchemaVersion": "raw_lexical_weights",
      "path": "DQA_CONTROL_PATH",
      "postProcessorVersion": "none",
      "queryInstruction": null,
      "returnColbertVecs": false,
      "returnDense": false,
      "returnSparse": true,
      "specialTokenFilterHash": "e6f6320962e4258dd14df72af9fcac867cf5610ad77e45ed2ee066405920745e",
      "useFp16": true
    },
    "ORIGINAL_INDEX_BUILDER_PATH": {
      "batchSizes": [
        1,
        8
      ],
      "device": "cuda",
      "encodeArgumentsHash": "9d601027639776a3bad38a75dff80cbfd03b931c21a661049d0b31f17a18b0bd",
      "encodeMethod": "project_encode_sparse",
      "instruction": null,
      "maxLength": 128,
      "minimumSparseWeight": 0.0,
      "modelClass": "FlagEmbedding.BGEM3FlagModel",
      "modelConstructorArgumentsHash": "27de6ae3da1136fd7c82eb429a873cbb5dcdee5634865fbb2744d7b1267706c3",
      "normalizeEmbeddings": false,
      "outputFieldName": "lexical_weights",
      "outputSchemaVersion": "normalized_int_token_weights",
      "path": "ORIGINAL_INDEX_BUILDER_PATH",
      "postProcessorVersion": "project-token-id-normalization-v1",
      "queryInstruction": null,
      "returnColbertVecs": false,
      "returnDense": false,
      "returnSparse": true,
      "specialTokenFilterHash": "e6f6320962e4258dd14df72af9fcac867cf5610ad77e45ed2ee066405920745e",
      "useFp16": true
    },
    "RCA_OFFICIAL_DIRECT_PATH": {
      "batchSizes": [
        1,
        8
      ],
      "device": "cuda",
      "encodeArgumentsHash": "9d601027639776a3bad38a75dff80cbfd03b931c21a661049d0b31f17a18b0bd",
      "encodeMethod": "FlagEmbedding.encode",
      "instruction": null,
      "maxLength": 128,
      "minimumSparseWeight": 0.0,
      "modelClass": "FlagEmbedding.BGEM3FlagModel",
      "modelConstructorArgumentsHash": "27de6ae3da1136fd7c82eb429a873cbb5dcdee5634865fbb2744d7b1267706c3",
      "normalizeEmbeddings": false,
      "outputFieldName": "lexical_weights",
      "outputSchemaVersion": "raw_lexical_weights",
      "path": "RCA_OFFICIAL_DIRECT_PATH",
      "postProcessorVersion": "none",
      "queryInstruction": null,
      "returnColbertVecs": false,
      "returnDense": false,
      "returnSparse": true,
      "specialTokenFilterHash": "e6f6320962e4258dd14df72af9fcac867cf5610ad77e45ed2ee066405920745e",
      "useFp16": true
    }
  },
  "schemaVersion": "agent-rag-v23-sparse-invocation-path-diff-v1"
}
```
